# -*- coding: utf-8 -*-
"""
GRPO training for Action Model with HuggingFace Transformers + PEFT (no unsloth, no vllm).
Uses Qwen3-14B with LoRA and parallel OpenAI scoring as reward.

Input columns:  PTT, New strategy, Strategy explanation
Output format:
    <think>brief reasoning (≤512 tokens)      </think>
    <action>Numbered 4-6 step action plan</action>
    <mcp_servers>["Server1", "Server2"]</mcp_servers>
    <mcp_usage>
    Server1:
    * Task description
    * Usage instructions
    * Expected results
    </mcp_usage>

Reward functions:
    1. format_reward              — structural tag / JSON validity check
    2. action_geval_reward        — GPT-4o-mini GEVal on Action quality vs ground truth
    3. mcp_server_matching_reward — Jaccard + F1 overlap of MCP server selection
    4. mcp_usage_geval_reward     — GPT-4o-mini GEVal per-server usage quality

Requirements:
    pip install transformers peft accelerate bitsandbytes pandas numpy tqdm safetensors torch datasets trl httpx openai nest_asyncio
Env:
    export OPENAI_API_KEY=sk-...
"""
import os, re, json, random, asyncio, time
from typing import List, Dict, Tuple, Optional, Set

import numpy as np
import pandas as pd
import torch
import re

from datasets import Dataset
from safetensors import safe_open
from trl import GRPOConfig, GRPOTrainer

from openai import AsyncOpenAI
import nest_asyncio

# ---------- Config ----------
SEED        = 2187

RPM             = 15
MAX_CONCURRENCY = 8
OPENAI_MODEL    = "gpt-4o-mini"
TIMEOUT_S       = 60

# ---------- Init ----------
torch.manual_seed(SEED)
np.random.seed(SEED)
random.seed(SEED)


if not os.environ.get("OPENAI_API_KEY"):
    raise ValueError("OPENAI_API_KEY environment variable not set.")


# ---------- Approved MCP servers ----------
APPROVED_SERVERS: Set[str] = {
    "Nmap", "Metasploit", "Netcat", "Dirbuster", "SQLmap", "SMB Client",
    "Hydra", "Burp Suite", "Hashcat", "Google Search", "File System Analysis",
    "ExploitDB", "Interactive CLI", "Web Page Analysis",
}
APPROVED_LIST_STR = ", ".join(sorted(APPROVED_SERVERS))

# ---------- Regex patterns ----------
RE_THINK       = re.compile(r"<think>(.*?)</think>",             re.DOTALL)
RE_ACTION      = re.compile(r"<action>(.*?)</action>",           re.DOTALL)
RE_MCP_SERVERS = re.compile(r"<mcp_servers>(.*?)</mcp_servers>", re.DOTALL)
RE_MCP_USAGE   = re.compile(r"<mcp_usage>(.*?)</mcp_usage>",     re.DOTALL)

# ---------- Parsing helpers ----------
def _extract_text(c) -> str:
    if isinstance(c, str): return c
    if isinstance(c, dict) and "content" in c: return c["content"]
    if isinstance(c, list) and c and isinstance(c[0], dict): return c[0]["content"]
    return str(c)


def _extract_sections(text: str) -> Dict[str, str]:
    return {
        "think":       (m.group(1).strip() if (m := RE_THINK.search(text))       else ""),
        "action":      (m.group(1).strip() if (m := RE_ACTION.search(text))      else ""),
        "mcp_servers": (m.group(1).strip() if (m := RE_MCP_SERVERS.search(text)) else ""),
        "mcp_usage":   (m.group(1).strip() if (m := RE_MCP_USAGE.search(text))   else ""),
    }


def _parse_server_list(raw: str) -> List[str]:
    """Parse a JSON array of server names; falls back to regex extraction."""
    text = raw.strip()
    for candidate in [text, text.replace("'", '"')]:
        try:
            result = json.loads(candidate)
            if isinstance(result, list):
                return [str(s).strip() for s in result if s]
        except Exception:
            pass
    return re.findall(r'["\']([^"\']+)["\']', text)


def _parse_usage_blocks(usage_text: str) -> Dict[str, str]:
    """
    Split MCP server usage text into per-server blocks.
    Recognises headers of the form 'ServerName:' on their own line.
    Case-insensitive matching against APPROVED_SERVERS.
    """
    lower_map = {s.lower(): s for s in APPROVED_SERVERS}
    blocks: Dict[str, str] = {}
    current: Optional[str] = None
    lines: List[str] = []

    for line in usage_text.split("\n"):
        stripped = line.strip()
        if stripped.endswith(":"):
            candidate = stripped[:-1].strip().lower()
            if candidate in lower_map:
                if current is not None:
                    blocks[current] = "\n".join(lines).strip()
                current = lower_map[candidate]
                lines = []
                continue
        if current is not None:
            lines.append(line)

    if current is not None:
        blocks[current] = "\n".join(lines).strip()
    return blocks

# ---------- OpenAI async helpers ----------
_client = AsyncOpenAI()


async def _sleep_for_rate_limit():
    base = 60.0 / max(1, RPM)
    await asyncio.sleep(random.uniform(0.0, base / 5))


async def _chat_once(prompt: str, max_retries: int = 5) -> str:
    delay = 1.0
    for attempt in range(1, max_retries + 1):
        try:
            resp = await _client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
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
    return ""


async def _chat_batch(prompts: List[str]) -> List[str]:
    sem = asyncio.Semaphore(MAX_CONCURRENCY)
    async def _task(p: str) -> str:
        async with sem:
            await _sleep_for_rate_limit()
            return await _chat_once(p)
    return list(await asyncio.gather(*[_task(p) for p in prompts]))


def _run_async(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError:
        nest_asyncio.apply()
        return asyncio.get_event_loop().run_until_complete(coro)


def _parse_score(text: str) -> float:
    text = (text or "").strip()
    
    # Strip markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    
    # Try direct parse first, then fallback to regex extraction
    for candidate in [text, re.search(r'\{.*\}', text, re.DOTALL) and re.search(r'\{.*\}', text, re.DOTALL).group()]:
        if not candidate:
            continue
        try:
            score = json.loads(candidate.strip()).get("score", None)
            if score is not None:
                return float(score)
        except Exception:
            continue
    
    return 0.0

# ---------- GEval prompt builders ----------
def _prompt_action_eval(strategy: str, ground_truth: str, generated: str, ptt: str = "") -> str:
    return f"""
You are a reward model evaluating an Action plan for a penetration testing strategy.
Penetration Testing Tree: {ptt}
Strategy: {strategy}

Score each criterion on [-2, 2]:
1) Coverage — does the generated plan cover the essential steps from the ground truth?
2) Result — does each action specify the result it expects as ground truth?

-2 = completely wrong/irrelevant, -1 = mostly incorrect, 1 = partially correct, +2 = excellent match or better

Return ONLY JSON: {{"score": <average of 2 scores>, "explanation": "<brief justification>"}}

GROUND TRUTH ACTION:
{ground_truth}

GENERATED ACTION:
{generated}
""".strip()


def _prompt_usage_eval(server: str, strategy: str, ground_truth: str, generated: str) -> str:
    return f"""
You are a reward model evaluating an MCP server usage explanation for a penetration testing step.

Server: {server}
Strategy: {strategy}

Score each criterion on [-2, 2]:
1) Task clarity — Does the candidate describe the same server task and purpose as the ground truth?
2) Expected results — Does the candidate accurately describe the expected outputs, findings, or observations specified in the ground truth?

-2 = completely wrong/missing, 0 = partially correct/generic, +2 = excellent and specific

Return ONLY JSON: {{"score": <average of 4 scores>, "explanation": "<brief justification>"}}

GROUND TRUTH USAGE:
{ground_truth}

GENERATED USAGE:
{generated}
""".strip()

# ---------- Dataset ----------
dataset = None

def _ensure_action_dataset(tokenizer_obj):
    global dataset
    if dataset is not None:
        return dataset

    raw_df = pd.read_csv("./../Data/training_data.csv")

    selected = ["PTT", "New strategy", "Strategy explanation", "Action", "MCP servers", "MCP server usage"]
    df = (raw_df[selected]
          .fillna("")
          .astype(str)
          .map(str.strip))
    df = df.sample(frac=1, random_state=SEED).reset_index(drop=True)

    system_prompt = (
        "You are a penetration testing action planner. "
        "Given the current PTT (Penetration Testing Tree), a new strategy, and its explanation, "
        "generate a concrete action plan to execute the strategy through reasoning, select the minimum required MCP servers, "
        "and explain how to use each one.\n\n"
        f"Available MCP servers: {APPROVED_LIST_STR}\n\n"
        "Output format (use these exact tags):\n"
        "<think>brief logical reasoning (reasoning < 512 tokens)      </think>\\n"
        "<action>\n"
        "1. First operational step\n"
        "2. Second operational step\n"
        "3. ..\n"
        "4. ..\n"
        "</action>\n"
        '<mcp_servers>["Server1", "Server2", ...]</mcp_servers>\n'
        "<mcp_usage>\n"
        "Server1:\n"
        "* Specific task it performs\n"
        "* How to use it (parameters, wordlists, modules)\n"
        "* Expected findings or results\n\n"
        "Server2:\n"
        "* Specific task it performs\n"
        "* How to use it\n"
        "* Expected findings or results\n"
        "Server..:\n"
        "..."
        "</mcp_usage>"
    )

    rows = []
    for _, r in df.iterrows():
        user_text = (
            f"<PTT>{r['PTT']}</PTT>\n"
            f"<New strategy>{r['New strategy']}</New strategy>\n"
            f"<Strategy explanation>{r['Strategy explanation']}</Strategy explanation>\n\n"
            "Analyze the attack environment(PTT) and the strategy and Generate the action plan, MCP servers, and usage instructions to execute this penetration testing strategy.\n"
            "Use the exact output format specified in the system prompt."
        )
        rows.append({
            "prompt": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_text},
            ],
            "answer_action":      r["Action"],
            "answer_mcp_servers": r["MCP servers"],
            "answer_mcp_usage":   r["MCP server usage"],
            "strategy":           r["New strategy"],
        })

    hf_ds = Dataset.from_list(rows)

    def to_example(ex):
        msgs = (ex["prompt"] if isinstance(ex["prompt"], list)
                else [{"role": ro, "content": co}
                      for ro, co in zip(ex["prompt"]["role"], ex["prompt"]["content"])])
        return {
            "prompt_text":        tokenizer_obj.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False),
            "answer_action":      ex["answer_action"],
            "answer_mcp_servers": ex["answer_mcp_servers"],
            "answer_mcp_usage":   ex["answer_mcp_usage"],
            "strategy":           ex["strategy"],
        }

    mapped = hf_ds.map(to_example, batched=False)

    def _add_len(batch):
        out = tokenizer_obj(batch["prompt_text"], add_special_tokens=False)
        return {"prompt_len": [len(ids) for ids in out["input_ids"]]}

    ds_len = mapped.map(_add_len, batched=True)
    max_len = int(np.quantile(ds_len["prompt_len"], 0.9))
    dataset = ds_len.filter(lambda x: x["prompt_len"] <= max_len)
    return dataset


# ---------- Reward 1: Format ----------
def format_reward(completions, **kwargs) -> List[float]:
    """
    Checks structural validity of the model output.

    Scoring (approx range [-5, 5]):
      ±0.5  each for <think> /       </think> (exactly once)
      ±1.0  for <action>...</action> present
      ±1.0  for <mcp_servers>...</mcp_servers> present
      ±1.0  for <mcp_usage>...</mcp_usage> present
      +1.0  bonus if MCP servers section parses as a valid JSON array of approved names
    """

    #print('\n\n-----------------\n\n', _extract_text(completions[0]))
    scores = []
    for c in completions:
        t = _extract_text(c)
        s = 0.0
        s += 0.5  if t.count("<think>")       == 1 else -0.5
        s += 0.5  if t.count("</think>")      == 1 else -0.5
        s += 1.0  if RE_ACTION.search(t)      else -1.0
        s += 1.0  if RE_MCP_SERVERS.search(t) else -1.0
        s += 1.0  if RE_MCP_USAGE.search(t)   else -1.0
        m = RE_MCP_SERVERS.search(t)
        if m:
            servers = _parse_server_list(m.group(1))
            if servers and all(sv in APPROVED_SERVERS for sv in servers):
                s += 1.0
            else:
                s -= 0.5
        scores.append(s/5)
    return scores


# ---------- Reward 2: Action GEval ----------
def action_geval_reward(completions, **kwargs) -> List[float]:
    batch      = kwargs.get("batch") or {}
    gt_actions = list(batch.get("answer_action") or kwargs.get("answer_action") or [])
    strategies = list(batch.get("strategy")      or kwargs.get("strategy")      or [])
    ptts       = list(batch.get("ptt")           or kwargs.get("ptt")           or [])

    texts = [_extract_text(c) for c in completions]
    bs = len(gt_actions)
    if bs == 0:
        print('bs length is zero.....')
        return [0.0] * len(texts)

    k            = max(1, len(texts) // bs)
    gt_actions_r = sum(([a] * k for a in gt_actions), [])
    strategies_r = sum(([s] * k for s in strategies),  [])
    ptts_r       = sum(([p] * k for p in ptts),        []) if ptts else [""] * len(texts)
    
    #print('\n\n action plan',_extract_sections(texts[0])["action"])

    async def _run():
        prompts = [
            _prompt_action_eval(strat, gt, _extract_sections(t)["action"], ptt)
            for strat, gt, t, ptt in zip(strategies_r, gt_actions_r, texts, ptts_r)
        ]
        return await _chat_batch(prompts)

    ACTION_W = 2.0
    raw = _run_async(_run())
    return [ACTION_W * _parse_score(r) for r in raw]


# ---------- Reward 3: MCP server matching ----------
def mcp_server_matching_reward(completions, **kwargs) -> List[float]:
    """
    Computes F1 + Jaccard similarity between generated and ground-truth MCP server lists.
    Penalises servers not in the approved list (-0.3 each).
    Range: ≈ [-2, 2].
    """
    batch       = kwargs.get("batch") or {}
    gt_mcp_strs = list(batch.get("answer_mcp_servers") or kwargs.get("answer_mcp_servers") or [])

    texts = [_extract_text(c) for c in completions]
    bs = len(gt_mcp_strs)
    if bs == 0:
        return [0.0] * len(texts)

    k           = max(1, len(texts) // bs)
    gt_mcp_rep  = sum(([g] * k for g in gt_mcp_strs), [])

    #print('\n\n extracted servers',set(_parse_server_list(_extract_sections(texts[0])["mcp_servers"])))

    scores = []
    for text, gt_str in zip(texts, gt_mcp_rep):
        gen_servers: Set[str] = set(_parse_server_list(_extract_sections(text)["mcp_servers"]))
        gt_servers:  Set[str] = set(s for s in _parse_server_list(gt_str) if s in APPROVED_SERVERS)

        if not gen_servers and not gt_servers:
            scores.append(0.0)
            continue

        invalid_penalty = -0.3 * len(gen_servers - APPROVED_SERVERS)

        intersection = gen_servers & gt_servers
        union        = gen_servers | gt_servers
        jaccard      = len(intersection) / len(union) if union else 0.0

        precision = len(intersection) / len(gen_servers) if gen_servers else 0.0
        recall    = len(intersection) / len(gt_servers)  if gt_servers  else 0.0
        f1        = (2 * precision * recall / (precision + recall)
                     if (precision + recall) > 0 else 0.0)

        # Average Jaccard + F1, map [0,1] → [-2,2]
        combined = ((jaccard + f1) / 2.0) * 4.0 - 2.0 + invalid_penalty
        scores.append(float(np.clip(combined, -2.0, 2.0)))

    return scores


# ---------- Reward 4: MCP server usage GEVal (per-server) ----------
def mcp_usage_geval_reward(completions, **kwargs) -> List[float]:
    """
    For each server in the ground-truth MCP selection, runs GPT-4o-mini GEVal
    comparing the generated usage block against the ground-truth usage block.
    Scores are averaged across matched servers; missing servers incur a -0.5 penalty each.

    USAGE_W * avg_score + missing_penalty, clipped to [-4, 4].
    """
    batch         = kwargs.get("batch") or {}
    gt_usage_strs = list(batch.get("answer_mcp_usage")    or kwargs.get("answer_mcp_usage")    or [])
    gt_mcp_strs   = list(batch.get("answer_mcp_servers")  or kwargs.get("answer_mcp_servers")  or [])
    strategies    = list(batch.get("strategy")             or kwargs.get("strategy")             or [])

    texts = [_extract_text(c) for c in completions]
    bs = len(gt_usage_strs)
    if bs == 0:
        return [0.0] * len(texts)

    k              = max(1, len(texts) // bs)
    gt_usage_rep   = sum(([u] * k for u in gt_usage_strs), [])
    gt_mcp_rep     = sum(([m] * k for m in gt_mcp_strs),   [])
    strategies_rep = sum(([s] * k for s in strategies),    [])

    # Build a flat list of GEVal prompts across all items and all servers
    all_prompts:   List[str]           = []
    item_metadata: List[Dict]          = []   # one entry per completion


    for text, gt_usage_str, gt_mcp_str, strat in zip(
        texts, gt_usage_rep, gt_mcp_rep, strategies_rep
    ):
        sections   = _extract_sections(text)
        gen_blocks = _parse_usage_blocks(sections["mcp_usage"])
        #print('\n\n',gen_blocks)
        gt_blocks  = _parse_usage_blocks(gt_usage_str)
        gt_servers = set(s for s in _parse_server_list(gt_mcp_str) if s in APPROVED_SERVERS)

        start = len(all_prompts)
        for server in gt_servers:
            all_prompts.append(
                _prompt_usage_eval(server, strat, gt_blocks.get(server, ""), gen_blocks.get(server, ""))
            )

        item_metadata.append({
            "start":      start,
            "count":      len(gt_servers),
            "gt_servers": gt_servers,
            "gen_blocks": gen_blocks,
        })

    if not all_prompts:
        return [0.0] * len(texts)

    raw_results = _run_async(_chat_batch(all_prompts))

    USAGE_W = 2.0
    final: List[float] = []
    for meta in item_metadata:
        count = meta["count"]
        if count == 0:
            final.append(0.0)
            continue

        per_server_scores = [
            _parse_score(raw_results[meta["start"] + i])
            for i in range(count)
        ]
        avg_score     = sum(per_server_scores) / len(per_server_scores)
        missing_count = sum(1 for s in meta["gt_servers"] if s not in meta["gen_blocks"])
        penalty       = -0.5 * missing_count

        final.append(float(np.clip(USAGE_W * avg_score + penalty, -4.0, 4.0)))

    return final


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


def train_action(current_model, dataset_part=None, output_dir="./../Trained_models/staged_final", max_steps=None, tokenizer_obj=None):
    if current_model is None or tokenizer_obj is None:
        raise ValueError("train_action requires a pre-built model and tokenizer_obj (build them once in staged_training.py).")
    model_to_use = current_model
    ds_work = _resolve_dataset_portion(_ensure_action_dataset(tokenizer_obj), dataset_part)

    MAX_PROMPT = 4000

    def _truncate(ex):
        enc = tokenizer_obj(
            ex["prompt_text"],
            add_special_tokens=False,
            truncation=True,
            max_length=MAX_PROMPT,
        )
        ex["prompt_text"] = tokenizer_obj.decode(enc["input_ids"], skip_special_tokens=True)
        ex["prompt_len"] = len(enc["input_ids"])
        return ex

    ds_final = ds_work.map(_truncate, batched=False)
    training_args = GRPOConfig(
        temperature                 = 0.7,
        learning_rate               = 5e-5,
        weight_decay                = 0.01,
        bf16                        = torch.cuda.is_available() and torch.cuda.is_bf16_supported(),
        fp16                        = torch.cuda.is_available() and not (torch.cuda.is_available() and torch.cuda.is_bf16_supported()),
        warmup_ratio                = 0.1,
        lr_scheduler_type           = "linear",
        optim                       = "adamw_8bit",
        logging_steps               = 1,
        per_device_train_batch_size = 8,
        gradient_accumulation_steps = 2,
        num_generations             = 4,
        max_completion_length       = 2048,
        num_train_epochs            = 2,
        max_steps                   = max_steps,
        save_steps                  = 50,
        disable_tqdm                = False,
        report_to                   = "none",
        output_dir                  = output_dir,
    )

    trainer = GRPOTrainer(
        model            = model_to_use,
        processing_class = tokenizer_obj,
        reward_funcs     = [
            format_reward,
            action_geval_reward,
            mcp_server_matching_reward,
            mcp_usage_geval_reward,
        ],
        args             = training_args,
        train_dataset    = ds_final,
    )
    trainer.train()
    return trainer


class ActionTrainer:
    def __init__(self, model=None):
        self.model = model

    def train(self, current_model=None, dataset_part=None, output_dir="./../Trained_models/staged_final", tokenizer_obj=None):
        model_to_use = current_model if current_model is not None else self.model
        if model_to_use is None or tokenizer_obj is None:
            raise ValueError("ActionTrainer.train requires a pre-built model and tokenizer_obj.")
        return train_action(model_to_use, dataset_part, output_dir, tokenizer_obj=tokenizer_obj)


def run_inference_demo(tokenizer_obj, active_model):
    demo_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": (
            "<PTT>1. Reconnaissance - [completed]\n"
            "   1.1 Active Information Gathering - (completed)\n"
            "   1.2 Port scan found port 80/tcp open — Apache HTTPD 2.4.18</PTT>\n"
            "<New strategy>Enumerate the HTTP service further to find hidden directories and files.</New strategy>\n"
            "<Strategy explanation>Port 80 is open running Apache HTTPD 2.4.18 on Ubuntu. "
            "The HTTP title suggests a development site which may expose hidden resources. "
            "Web content discovery should be performed to find interesting endpoints.</Strategy explanation>\n\n"
            "Generate the action plan, MCP servers, and usage instructions for this penetration testing step."
        )},
    ]
    text   = tokenizer_obj.apply_chat_template(demo_messages, add_generation_prompt=True, tokenize=False)
    inputs = tokenizer_obj(text, return_tensors="pt").to(active_model.device)

    active_model.eval()
    with torch.no_grad():
        out_ids = active_model.generate(**inputs, max_new_tokens=1024, temperature=1.0, top_k=50, do_sample=True)
    output = tokenizer_obj.decode(out_ids[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)

    print("\n=== Inference (with LoRA) ===\n", output)

    with active_model.disable_adapter():
        with torch.no_grad():
            out_ids_base = active_model.generate(**inputs, max_new_tokens=1024, temperature=1.0, top_k=50, do_sample=True)
    output_base = tokenizer_obj.decode(out_ids_base[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)

    print("\n=== Inference (base) ===\n", output_base)
