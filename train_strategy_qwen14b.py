# -*- coding: utf-8 -*-
"""
GRPO training with HuggingFace Transformers + PEFT (no unsloth, no vllm).
Uses Qwen3-14B with LoRA and parallel OpenAI scoring as reward.

Requirements:
  pip install transformers peft accelerate bitsandbytes pandas numpy tqdm langid safetensors torch datasets trl httpx openai
Env:
  export OPENAI_API_KEY=sk-...
"""
import os, re, json, math, random, asyncio
from typing import List, Dict, Any, Tuple, Optional

import numpy as np
import pandas as pd
from tqdm import tqdm
import langid
import torch

from datasets import Dataset, Features, Sequence, Value
from safetensors import safe_open
from trl import GRPOConfig, GRPOTrainer

import openai
from openai import OpenAI

# ---------- Config ----------
SEED        = 2187

# OpenAI rate/parallelism (tune to your quota)
RPM                 = 15          # requests per minute allowed
MAX_CONCURRENCY     = 8           # parallel requests in flight
OPENAI_CHAT_MODEL   = "gpt-4o-mini"
OPENAI_EMBED_MODEL  = "text-embedding-3-small"
TIMEOUT_S           = 60
USE_OPENAI_EMBEDDINGS = False      # set False if you swap to a local embedding model later

# ---------- Init ----------
torch.manual_seed(SEED)
np.random.seed(SEED)
random.seed(SEED)

tokenizer = None


# ---------- Reasoning tags & regex ----------
REASONING_START = "<think>"
REASONING_END   = "</think>"
RE_THINK = re.compile(rf"{re.escape(REASONING_START)}(.*?){re.escape(REASONING_END)}", re.DOTALL)
RE_TAIL  = re.compile(rf"{re.escape(REASONING_END)}(.*)$", re.DOTALL)


def extract_strategy_exp(text: str, chat_model: str = "gpt-3.5-turbo"):

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    prompt = f"""
    You are given a text, extract the strategy and explanation from the text.
    You should not invent any new text, only extract from the given text. 
    

    Respond ONLY in JSON format like:
    {{
        "strategy": extracted strategy,
        "explanation": extracted explanation
    }}
    
    Input text:
    {text}
    """

    response = client.chat.completions.create(
        model=chat_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )

    try:
        scores = json.loads(response.choices[0].message.content.strip())
        strategy = str(scores.get("strategy", ""))
        explanation = str(scores.get("explanation", ""))
    except Exception:
        strategy = ""
        explanation = ""

    return strategy, explanation


def split_output(text: str) -> Tuple[str, str]:
    """Return (strategy_after_think, explanation_inside_think)."""
    if not isinstance(text, str):
        text = str(text)
    m_ans = RE_TAIL.search(text)
    m_exp = RE_THINK.search(text)
    if m_ans:
        strategy, explanation = extract_strategy_exp(m_ans.group(1))
        explanation = m_exp.group(1) if m_exp else explanation
    else:
        strategy, explanation = extract_strategy_exp(text)

    return strategy, explanation


def _extract_text(c):
    if isinstance(c, str): return c
    if isinstance(c, dict) and "content" in c: return c["content"]
    if isinstance(c, list) and c and isinstance(c[0], dict) and "content" in c[0]: return c[0]["content"]
    return str(c)

# ---------- OpenAI async helpers ----------
from openai import AsyncOpenAI
_client = AsyncOpenAI()   # reads OPENAI_API_KEY from environment

async def _sleep_for_rate_limit():
    # Simple pacing: keep under RPM with a bit of jitter
    base = 60.0 / max(1, RPM)
    await asyncio.sleep(random.uniform(0.0, base / 5))

async def _chat_once(prompt: str, model: str = OPENAI_CHAT_MODEL, temperature: float = 0.0, max_retries: int = 5) -> str:
    delay = 1.0
    for attempt in range(1, max_retries + 1):
        try:
            resp = await _client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                timeout=TIMEOUT_S,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            msg = str(e).lower()
            retriable = any(k in msg for k in ["429", "timeout", "temporarily", "overloaded", "502", "503", "504"])
            if not retriable or attempt == max_retries:
                return ""
            await asyncio.sleep(delay + random.uniform(0, 0.25 * delay))
            delay = min(delay * 2, 8.0)

async def chat_batch(prompts: List[str], model: str = OPENAI_CHAT_MODEL, temperature: float = 0.0, max_concurrency: int = MAX_CONCURRENCY) -> List[str]:
    sem = asyncio.Semaphore(max_concurrency)
    async def _task(p: str):
        async with sem:
            await _sleep_for_rate_limit()
            return await _chat_once(p, model=model, temperature=temperature)
    return await asyncio.gather(*[_task(p) for p in prompts])

async def embed_batch_async(texts: List[str], model: str = OPENAI_EMBED_MODEL, batch_size: int = 256) -> List[np.ndarray]:
    vecs: List[np.ndarray] = []
    for i in range(0, len(texts), batch_size):
        chunk = texts[i:i + batch_size]
        resp = await _client.embeddings.create(model=model, input=chunk, timeout=TIMEOUT_S)
        vecs.extend([np.array(d.embedding, dtype=np.float32) for d in resp.data])
        await asyncio.sleep(max(0.0, 60.0 / max(1, RPM) / 2))
    return vecs

def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))

# ---------- Data ----------
dataset = None

def _ensure_strategy_dataset(tokenizer_obj):
    global dataset
    if dataset is not None:
        return dataset

    original_dataset  = pd.read_csv('./../Data/training_data.csv')

    selected_columns = ['PTT', 'Previous step', 'Previous step result', 'New strategy', 'Strategy explanation']
    df = (original_dataset[selected_columns]
          .fillna("")
          .astype(str)
          .map(lambda s: s.strip()))
    df = df.sample(frac=1, random_state=32).reset_index(drop=True)

    system_prompt = (
        "You are a penetration testing strategist. Using the previous findings (PTT), "
        "Previous step and the Previous step results, derive a New strategy for the next step in the pentesting process. "
        "Output format: <think>brief logical reasoning (<=512 tokens) </think>Final strategy"
    )

    rows = []
    for _, r in df.iterrows():
        user_text = (
            f"<PTT>{r['PTT']}</PTT>\n"
            f"<Previous step>{r['Previous step']}</Previous step>\n"
            f"<Previous step result>{r['Previous step result']}</Previous step result>\n"
            f"Derive a New strategy for the next step in the pentesting process based on the previous step and findings. "
            f"Output format: {REASONING_START} brief logical reasoning, explaining the final strategy {REASONING_END}Final strategy"
        )
        rows.append({
            "prompt": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_text},
            ],
            "answer": r['New strategy'],
            "explanation": r['Strategy explanation'],
        })

    features = Features({
        "prompt": Sequence({"role": Value("string"), "content": Value("string")}),
        "answer": Value("string"),
        "explanation": Value("string"),
    })
    hf_ds = Dataset.from_list(rows)

    def to_example(ex):
        msgs = ex["prompt"] if isinstance(ex["prompt"], list) else [{"role": r, "content": c} for r, c in zip(ex["prompt"]["role"], ex["prompt"]["content"])]
        prompt_text = tokenizer_obj.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
        return {"prompt_text": prompt_text, "answer": ex.get("answer", ""), "explanation": ex.get("explanation", "")}

    mapped = hf_ds.map(to_example, batched=False)

    def add_len(batch):
        out = tokenizer_obj(batch["prompt_text"], add_special_tokens=False)
        return {"prompt_len": [len(ids) for ids in out["input_ids"]]}

    ds_len = mapped.map(add_len, batched=True)
    max_len = int(np.quantile(ds_len["prompt_len"], 0.9))
    dataset = ds_len.filter(lambda x: x["prompt_len"] <= max_len)
    return dataset


# ---------- Rewards ----------
def explanation_length_reward_fn(expl: Optional[str]) -> float:
    max_reward = 1.0
    min_reward = -1.0
    slope = 0.5
    max_tokens = 768
    if not expl:
        return 0.0
    ids = tokenizer(expl, add_special_tokens=False)["input_ids"]
    n = len(ids)
    over = max(0, n - max_tokens)
    s = max_reward - slope * (over / max_tokens)
    return float(np.clip(s, min_reward, max_reward))

def format_exact(completions, **kwargs):
    texts = [_extract_text(c) for c in completions]
    scores = []
    for t in texts:
        s = 0.0
        if RE_TAIL.search(t) is not None:   # has          </think> then strategy
            s += 2.0
        scores.append(s)
    return scores

def format_approx(completions, **kwargs):
    texts = [_extract_text(c) for c in completions]
    out = []
    for t in texts:
        s = 0.0
        s += 0.5 if t.count(REASONING_START) == 1 else -1.0
        s += 0.5 if t.count(REASONING_END)   == 1 else -1.0
        out.append(s)
    return out

def get_lang(text: str) -> str:
    if not text: return "und"
    lang, _ = langid.classify(text)
    return lang.split("-")[0].lower()

TARGET_LANG = "en"
def language_reward(completions, **kwargs):
    out = []
    for t in (_extract_text(c) for c in completions):
        if not isinstance(t, str) or not t.strip():
            out.append(-1.0)
            continue
        lang = get_lang(t)
        out.append(1.0 if lang == TARGET_LANG else 0.0)
    return out


def _rm_prompt_explanation(ground_truth: str, generated: str) -> str:
    return f"""
You are a reward model judging ONLY the EXPLANATION (reasoning inside    <think>...          </think>).
Compare GENERATED explanation vs GROUND TRUTH explanation for a penetration test step.

Score each criterion in [-2,2]:
1) Logical alignment with the ground truth rationale
2) References similar evidence/findings or constraints
3) Leads to the same final decision for the stated context
4) Technical plausibility and absence of contradictions

Return ONLY JSON:
{{"score": <average of 4 scores>, "explanation": <brief explanation>}}

GROUND TRUTH EXPLANATION:
{ground_truth}

GENERATED EXPLANATION:
{generated}
""".strip()

def _rm_prompt_strategy(ground_truth: str, generated: str) -> str:
    return f"""
    You are a reward model. Compare GENERATED vs GROUND TRUTH for a pentest strategy.

    Score each criterion in [-2,2]:
    1) Coverage of essential technical terms/entities
    2) Same primary task
    3) Same expected outcome/deliverable
    4) Uses equivalent tools/techniques/procedures

    Based on the above analysis, provide individual scores (between -2 and +2) for each point.
        - If completely disagree or negative, give -2.
        - If somewhat agrees or moderate, give 0.
        - If positive and mostly follows the GROUND TRUTH, give 1.
        - If completely agrees and exactly follows the GROUND TRUTH, give 2.
        
        Finally output the average of the points given for each question above.

    Respond ONLY in JSON format like:
    {{
        "score": 0.85,
        "explanation": brief justification in text
    }}

    GROUND TRUTH:
    {ground_truth}

    GENERATED:
    {generated}
    """.strip()

def _cosine_matrix(A: List[np.ndarray], B: List[np.ndarray]) -> List[float]:
    out = []
    for a, b in zip(A, B):
        out.append(cosine(a, b))
    return out

def _check_answer_parallel(prompts, completions, *, batch=None, **kwargs):
    """
    GRPO reward: GPT-based scoring for BOTH final strategy and explanation, run in parallel.
    No embeddings are used. Keeps async batching + retries under the hood.
    """
    answers = (batch or {}).get("answer") or kwargs.get("answer")
    exps    = (batch or {}).get("explanation") or kwargs.get("explanation")
    if answers is None or exps is None:
        raise ValueError("check_answer requires 'answer' and 'explanation'.")

    texts = [_extract_text(c) for c in completions]
    bs = len(answers)
    if bs == 0:
        return [0.0] * len(texts)

    # Number of generations per prompt
    k = max(1, len(texts) // bs)
    answers_rep = sum(([a] * k for a in answers), [])
    exps_rep    = sum(([e] * k for e in exps),    [])

    # Parse predictions into (strategy, explanation)
    pred_strats, pred_exps = [], []
    for t in texts:
        s, e = split_output(t)
        pred_strats.append(s)
        pred_exps.append(e)

    # Build two reward-model prompt lists (strategy & explanation)
    strat_rm_prompts = [_rm_prompt_strategy(gt or "", gen or "") for gt, gen in zip(answers_rep, pred_strats)]
    expl_rm_prompts  = [_rm_prompt_explanation(gt or "", gen or "") for gt, gen in zip(exps_rep, pred_exps)]

    # Run both batches in parallel (and keep order)
    async def _run_both():
        return await asyncio.gather(
            chat_batch(strat_rm_prompts, model=OPENAI_CHAT_MODEL, temperature=0.0, max_concurrency=MAX_CONCURRENCY),
            chat_batch(expl_rm_prompts,  model=OPENAI_CHAT_MODEL, temperature=0.0, max_concurrency=MAX_CONCURRENCY),
        )

    try:
        strat_texts, expl_texts = asyncio.run(_run_both())
    except RuntimeError:
        import nest_asyncio; nest_asyncio.apply()
        loop = asyncio.get_event_loop()
        strat_texts, expl_texts = loop.run_until_complete(_run_both())

    # Parse JSON scores
    def _parse_scores(batch_texts: list[str]) -> list[float]:
        out = []
        for s in batch_texts:
            try:
                obj = json.loads((s or "").strip())
                out.append(float(obj.get("score", 0.0)))
            except Exception:
                out.append(0.0)
        return out

    strat_scores = _parse_scores(strat_texts)   # strategy RM scores
    expl_scores  = _parse_scores(expl_texts)    # explanation RM scores

    # Explanation length bonus/penalty
    len_bonus = [explanation_length_reward_fn(e) for e in pred_exps]

    # Combine: emphasize strategy, keep explanation + length as supportive
    STRAT_W, EXPL_W, LEN_W = 3.0, 2.0, 1.0
    scores = [
        STRAT_W * s + EXPL_W * e + LEN_W * lb
        for s, e, lb in zip(strat_scores, expl_scores, len_bonus)
    ]
    return scores

# ---------- GRPO Training ----------
def _resolve_dataset_portion(dataset_obj, portion):
    if portion is None:
        return dataset_obj
    if isinstance(portion, slice):
        return dataset_obj.select(range(*portion.indices(len(dataset_obj))))
    if isinstance(portion, int):
        return dataset_obj.select(range(min(portion, len(dataset_obj))))
    if isinstance(portion, (list, tuple)):
        return dataset_obj.select(list(portion))
    return dataset_obj


def train_strategy(current_model, dataset_part=None, output_dir="./../Trained_models/GDPO_Qwen14B", max_steps=None, tokenizer_obj=None):
    global tokenizer
    if current_model is None or tokenizer_obj is None:
        raise ValueError("train_strategy requires a pre-built model and tokenizer_obj (build them once in staged_training.py).")
    model_to_use = current_model
    tokenizer = tokenizer_obj
    ds_work = _resolve_dataset_portion(_ensure_strategy_dataset(tokenizer_obj), dataset_part)

    MAX_PROMPT = 3800

    def truncate_and_add_len(ex):
        enc = tokenizer_obj(
            ex["prompt_text"],
            add_special_tokens=False,
            truncation=True,
            max_length=MAX_PROMPT,
        )
        ex["prompt_text"] = tokenizer_obj.decode(enc["input_ids"], skip_special_tokens=True)
        ex["prompt_len"] = len(enc["input_ids"])
        return ex

    ds_single = ds_work.map(truncate_and_add_len, batched=False)
    max_seen = max(ds_single["prompt_len"])

    # trl>=1.0 / transformers>=5.0 dropped warmup_ratio from GRPOConfig (only
    # warmup_steps remains); compute the equivalent absolute step count so this
    # works whether warmup_ratio is available or not.
    warmup_steps = max(1, int(0.1 * max_steps)) if max_steps else 0

    training_args = GRPOConfig(
        temperature = 0.7,
        learning_rate = 5e-5,
        weight_decay = 0.01,
        warmup_steps = warmup_steps,
        lr_scheduler_type = "linear",
        optim = "adamw_8bit",
        logging_steps = 1,
        per_device_train_batch_size = 8,
        gradient_accumulation_steps = 2,
        num_generations = 4,
        max_completion_length = 1024,
        num_train_epochs = 3,
        max_steps = max_steps,
        save_steps = 50,
        disable_tqdm = False,
        report_to = "none",
        output_dir = output_dir,
    )

    trainer = GRPOTrainer(
        model = model_to_use,
        processing_class = tokenizer_obj,
        reward_funcs = [
            format_approx,
            _check_answer_parallel,
            language_reward,
        ],
        args = training_args,
        train_dataset = ds_single,
    )
    trainer.train()
    return trainer


class StrategyTrainer:
    def __init__(self, model=None):
        self.model = model

    def train(self, current_model=None, dataset_part=None, output_dir="./../Trained_models/GDPO_Qwen14B", tokenizer_obj=None):
        model_to_use = current_model if current_model is not None else self.model
        if model_to_use is None or tokenizer_obj is None:
            raise ValueError("StrategyTrainer.train requires a pre-built model and tokenizer_obj.")
        return train_strategy(model_to_use, dataset_part, output_dir, tokenizer_obj=tokenizer_obj)


def run_inference_demo(tokenizer_obj, active_model):
    # ---------- Save LoRA ----------
    active_model.save_pretrained("grpo_lora_14B")
    tokenizer_obj.save_pretrained("grpo_lora_14B")

    # Verify non-zero LoRA tensors
    with safe_open("grpo_lora_14B/adapter_model.safetensors", framework="pt") as f:
        for key in f.keys():
            tensor = f.get_tensor(key)
            n_zeros = (tensor == 0).sum() / tensor.numel()
            assert n_zeros.item() != tensor.numel(), f"LoRA tensor all zeros: {key}"

    # ---------- Inference demo ----------
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": "Solve (x + 2)^2 = 0"},
    ]
    text = tokenizer_obj.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
    inputs = tokenizer_obj(text, return_tensors="pt").to(active_model.device)

    gen_kwargs = dict(max_new_tokens=512, temperature=1.0, top_k=50, do_sample=True)

    # With LoRA
    active_model.eval()
    with torch.no_grad():
        out_ids = active_model.generate(**inputs, **gen_kwargs)
    out_with = tokenizer_obj.decode(out_ids[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)

    # Base model (LoRA adapters disabled)
    with active_model.disable_adapter():
        with torch.no_grad():
            out_ids_base = active_model.generate(**inputs, **gen_kwargs)
    out_base = tokenizer_obj.decode(out_ids_base[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)

    print("\n=== Inference (with LoRA) ===\n", out_with)
    print("\n=== Inference (base) ===\n", out_base)
