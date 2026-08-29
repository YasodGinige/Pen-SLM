# -*- coding: utf-8 -*-
"""
Inference for trained Qwen3-32B + LoRA (without Unsloth).
- Generates next "strategy" with a brief <think> explanation from test rows
- Computes G-EVAL similarity for both "strategy" and "strategy explanation"
- Saves per-sample results to CSV

Requirements:
  pip install transformers peft pandas numpy openai tqdm torch safetensors
  export OPENAI_API_KEY=sk-...
"""

import os
import re
import json
import random
from typing import Dict, Any, Optional, Tuple, List
import csv

import numpy as np
import pandas as pd
from tqdm import tqdm

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
from openai import OpenAI


# -----------------------------
# CONFIG
# -----------------------------
BASE_MODEL_NAME = "Qwen/Qwen3-14B"
LORA_PATH       = "./../../Trained_models/Pen-SLM"   # path to saved LoRA adapter
ORIGINAL_CSV        = "./../../Data/test_data.csv"
OUTPUT_CSV      = "./../Results/Pen-SLM_test-set_strategy.csv"

MAX_SEQ_LENGTH = 4000
MAX_PROMPT_TOKENS = 3800
SEED = 3407


# Columns expected in CSVs
COL_PTT = "PTT"
COL_PREV = "Previous step"
COL_PREV_RES = "Previous step result"
COL_STRATEGY = "New strategy"
COL_EXPLANATION = "Strategy explanation"

# Generation params
MAX_NEW_TOKENS = 2500
TEMPERATURE = 0.7
TOP_P = 1.0
TOP_K = 1

# Optional hardcode
os.environ["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY", "")

# Reproducibility
torch.manual_seed(SEED)
np.random.seed(SEED)
random.seed(SEED)

# System prompt (UNCHANGED)
SYSTEM_PROMPT = (
    """You are a penetration testing strategist. Using the previous findings (PTT), Previous step and the Previous step results, derive a New strategy for the next in the prentesting process through logical reasoning consistent with the previous findings in the PTT.
"""
)

REASONING_START = "<think>"
REASONING_END = "</think>"

# -----------------------------
# OpenAI client
# -----------------------------
client = OpenAI()

# -----------------------------
# G-EVAL dimensions (UNCHANGED)
# -----------------------------
DIMENSIONS = [
    {
        "id": "keywords",
        "name": "Technical Keywords",
        "rubric": (
            "Does the GENERATED cover the essential technical terms and entities that appear "
            "in the GROUND TRUTH (including domain-specific terminology, "
            "and notational conventions)?"
        ),
    },
    {
        "id": "task_alignment",
        "name": "Main Task Alignment",
        "rubric": (
            "Does the GENERATED perform or directly address the same primary task described "
            "in the GROUND TRUTH (purpose, objective, and problem framing)?"
        ),
    },
    {
        "id": "expected_outcome",
        "name": "Expected Outcome",
        "rubric": (
            "Does the GENERATED produce the same expected outcome or deliverable implied by "
            "the GROUND TRUTH (including structure, constraints, and acceptance criteria)?"
        ),
    },
    {
        "id": "methods_tools",
        "name": "Methods & Tools",
        "rubric": (
            "Does the GENERATED use (or explicitly reference) equivalent tools, techniques, "
            "or procedures to those in the GROUND TRUTH?"
        ),
    },
]

SYSTEM_PROMPT_EVAL = """You are an expert evaluator following the G-EVAL framework.
Evaluate a GENERATED text against a GROUND TRUTH across clearly defined dimensions through reasoning.
You MUST:
- Use the provided rubrics.
- Score each dimension on a 1–5 Likert scale (1=not aligned, 5=perfectly aligned).
- Provide a SHORT justification per dimension (one sentence).
- Output ONLY a single valid JSON object, no extra text.
- Do NOT reveal chain-of-thought; keep justifications concise and outcome-focused.
"""

USER_PROMPT_TEMPLATE = """You will evaluate GENERATED vs GROUND TRUTH.

Dimensions & rubrics:
{dimensions_block}

GROUND TRUTH:
---
{ground_truth}
---

GENERATED:
---
{generated}
---

Return ONLY valid JSON in this schema:
{{
  "dimension_scores": {{
    "keywords": {{"score": 1-5, "justification": "string"}},
    "task_alignment": {{"score": 1-5, "justification": "string"}},
    "expected_outcome": {{"score": 1-5, "justification": "string"}},
    "methods_tools": {{"score": 1-5, "justification": "string"}}
  }}
}}
"""


# -----------------------------
# Utility functions (UNCHANGED)
# -----------------------------
def _dimensions_block() -> str:
    lines = []
    for d in DIMENSIONS:
        lines.append(f"- {d['name']} ({d['id']}): {d['rubric']}")
    return "\n".join(lines)


def _normalize_1_to_5(score: float) -> float:
    score = max(1.0, min(5.0, float(score)))
    return (score - 1.0) / 4.0


def _safe_json_parse(s: str) -> Optional[Dict[str, Any]]:
    s = s.strip()
    try:
        return json.loads(s)
    except Exception:
        pass

    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(s[start:end + 1])
        except Exception:
            return None
    return None


def _content_to_text(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        out = []
        for p in content:
            if isinstance(p, dict):
                if p.get("type") == "text" and "text" in p:
                    out.append(p["text"])
                elif p.get("type") == "refusal" and "refusal" in p:
                    out.append(p["refusal"])
        return "".join(out)

    return str(content)


# -----------------------------
# G-EVAL scoring (UNCHANGED)
# -----------------------------
def compute_context_similarity_geval(
    ground_truth: str,
    generated: str,
    *,
    api_key: Optional[str] = None,
    model: str = "gpt-4o-mini",
) -> Dict[str, Any]:

    client_local = OpenAI(api_key=api_key)

    user_prompt = USER_PROMPT_TEMPLATE.format(
        dimensions_block=_dimensions_block(),
        ground_truth=ground_truth,
        generated=generated,
    )

    resp = client_local.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_EVAL},
            {"role": "user", "content": user_prompt},
        ],
        top_p=TOP_P,
    )

    msg = resp.choices[0].message
    content = _content_to_text(getattr(msg, "content", None)).strip()

    data = _safe_json_parse(content)
    if not data or "dimension_scores" not in data:
        return {"final_score": 0.0}

    norm_scores = []
    for d in DIMENSIONS:
        entry = data["dimension_scores"].get(d["id"], {})
        s = entry.get("score", 1)
        try:
            s_int = int(s)
        except Exception:
            s_int = 1
        s_int = max(1, min(5, s_int))
        norm_scores.append(_normalize_1_to_5(s_int))

    return {
        "final_score": round(sum(norm_scores) / len(norm_scores), 4)
    }


def compute_context_similarity(gt: str, gen: str) -> float:
    return float(compute_context_similarity_geval(gt, gen)["final_score"])


# -----------------------------
# Model loading (UNCHANGED)
# -----------------------------
print("Loading tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_NAME, trust_remote_code=True)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token
tokenizer.padding_side = "left"

print("Loading base model...")
model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL_NAME,
    device_map="auto",
    trust_remote_code=True,
    torch_dtype=torch.bfloat16,
)

print("Loading LoRA adapter...")
model = PeftModel.from_pretrained(model, LORA_PATH)
model.eval()


# -----------------------------
# Data loading (UNCHANGED)
# -----------------------------
df = pd.read_csv(ORIGINAL_CSV).fillna("")


df = df.sample(frac=1, random_state=SEED).reset_index(drop=True)

df = df[[COL_PTT, COL_PREV, COL_PREV_RES, COL_STRATEGY, COL_EXPLANATION]].fillna("")


# -----------------------------
# Prompt (UNCHANGED)
# -----------------------------
def build_user_prompt(ptt: str, prev_step: str, prev_res: str) -> str:
    return (
        f"<PTT>{ptt}</PTT>\n"
        f"<Previous step>{prev_step}</Previous step>\n"
        f"<Previous step result>{prev_res}</Previous step result>\n"
        "Derive a New strategy for the next step in the pentesting process based on the previous step and the findings. The derivation explanation must be limited to 512 tokens.\n"
        "The output must be in the following format;"
        "<think> brief logical reasoning, explaining the final solution</think>Final solution"
    )


def to_chat_text(system_prompt: str, user_content: str) -> str:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
    return tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=False,
    )


def truncate_prompt(text: str, tokenizer, max_tokens: int = MAX_PROMPT_TOKENS) -> str:
    ids = tokenizer(text, add_special_tokens=False)["input_ids"]
    if len(ids) > max_tokens:
        ids = ids[:max_tokens]
    return tokenizer.decode(ids, skip_special_tokens=False)


# -----------------------------
# OUTPUT PARSING (UNCHANGED)
# -----------------------------
RE_THINK = re.compile(rf"{re.escape(REASONING_START)}(.*?){re.escape(REASONING_END)}", re.DOTALL)
RE_TAIL = re.compile(rf"{re.escape(REASONING_END)}(.*)$", re.DOTALL)


def parse_output(text: str) -> Tuple[str, str]:
    text = str(text).strip()

    m_exp = RE_THINK.search(text)
    m_ans = RE_TAIL.search(text)

    explanation = ""
    strategy = ""

    if m_exp:
        explanation = m_exp.group(1).strip()

    if m_ans:
        strategy = m_ans.group(1).strip()

    return strategy, explanation


# -----------------------------
# SINGLE GENERATION (UPDATED)
# -----------------------------
def generate_single(text: str) -> str:
    enc = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=MAX_PROMPT_TOKENS,
    )

    input_ids = enc["input_ids"].to(model.device)
    attention_mask = enc["attention_mask"].to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            input_ids=input_ids,
            attention_mask=attention_mask,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=True,
            temperature=TEMPERATURE,
            top_p=TOP_P,
            top_k=TOP_K,
            eos_token_id=tokenizer.eos_token_id,
            pad_token_id=tokenizer.pad_token_id,
            use_cache=True,
        )

    gen_ids = outputs[0][input_ids.shape[1]:]
    return tokenizer.decode(gen_ids, skip_special_tokens=False)


# -----------------------------
# RUN
# -----------------------------
df["_user_prompt"] = [
    build_user_prompt(ptt, prev, prev_res)
    for ptt, prev, prev_res in zip(df[COL_PTT], df[COL_PREV], df[COL_PREV_RES])
]

df["_chat_text"] = [
    truncate_prompt(to_chat_text(SYSTEM_PROMPT, u), tokenizer)
    for u in df["_user_prompt"]
]

rows = []

print("Generating + evaluating...")

for ptt, prompt, ref_strat, ref_exp in tqdm(
    zip(df[COL_PTT], df["_chat_text"], df[COL_STRATEGY], df[COL_EXPLANATION]),
    total=len(df)
):

    gen = generate_single(prompt)

    strategy, explanation = parse_output(gen)

    try:
        s_exp = compute_context_similarity(ref_exp, explanation)
    except Exception:
        s_exp = 0.0

    try:
        s_str = compute_context_similarity(ref_strat, strategy)
    except Exception:
        s_str = 0.0

    rows.append({
        "ptt": ptt,
        "generated_full": gen,
        "parsed_strategy": strategy,
        "parsed_explanation": explanation,
        "similarity_strategy_geval": s_str,
        "similarity_explanation_geval": s_exp,
        "final_score": (s_str + s_exp) / 2.0,
        "gt_strategy": ref_strat,
        "gt_explanation": ref_exp,
    })


out_df = pd.DataFrame(rows)
out_df.to_csv(OUTPUT_CSV, index=False, quoting=csv.QUOTE_ALL, escapechar="\\", encoding="utf-8")

print(f"Saved: {OUTPUT_CSV}")

print("—— Summary ——")
print("Mean strategy similarity:", out_df["similarity_strategy_geval"].mean())
print("Mean explanation similarity:", out_df["similarity_explanation_geval"].mean())
print("Missed strategies:", (out_df["parsed_strategy"] == "").sum())