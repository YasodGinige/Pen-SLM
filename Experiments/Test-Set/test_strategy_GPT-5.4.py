# -*- coding: utf-8 -*-
"""
Same strategy-generation eval as test_strategy_Pen-SLM.py, but with GPT-5.4
(a hosted OpenAI model) as the generator under test instead of the local
Qwen3 + Pen-SLM LoRA adapter. The G-EVAL judge (gpt-4o-mini), data loading,
prompt construction, and output parsing are all unchanged.
- Generates next "strategy" with a brief <think> explanation from test rows
- Computes G-EVAL similarity for both "strategy" and "strategy explanation"
- Saves per-sample results to CSV

Requirements:
  pip install pandas numpy openai tqdm
  export OPENAI_API_KEY=sk-...
"""

import os
import re
import json
import random
from typing import Dict, Any, Optional, Tuple
import csv

import numpy as np
import pandas as pd
from tqdm import tqdm

from openai import OpenAI


# -----------------------------
# CONFIG
# -----------------------------
# Model under test. Adjust this if "gpt-5.4" isn't the exact model id your
# OpenAI account has access to -- everything else in this script is agnostic
# to which chat-completions-compatible model id you put here.
GENERATOR_MODEL = "gpt-5.4"

MAX_NEW_TOKENS = 2500
TEMPERATURE = 0.7
TOP_P = 1.0
SEED = 3407

# Data paths
ORIGINAL_CSV = "Data/processed_data_test.csv"
AUGMENTED_CSV = "Data/test_claude.csv"
USE_AUGMENTED_TOO = True
OUTPUT_CSV = "Results/results_GPT-5.4_strategy.csv"

# Columns expected in CSVs
COL_PTT = "PTT"
COL_PREV = "Previous step"
COL_PREV_RES = "Previous step result"
COL_STRATEGY = "New strategy"
COL_EXPLANATION = "Strategy explanation"

# Optional hardcode
os.environ["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY", "")

# Reproducibility (row sampling only -- there's no local model/sampler to seed)
np.random.seed(SEED)
random.seed(SEED)

# System prompt (UNCHANGED from test_strategy_Pen-SLM.py)
SYSTEM_PROMPT = (
    """You are a penetration testing strategist. Using the previous findings (PTT), Previous step and the Previous step results, derive a New strategy for the next in the prentesting process through logical reasoning consistent with the previous findings in the PTT.
"""
)

REASONING_START = "<think>"
REASONING_END = "</think>"

# -----------------------------
# OpenAI client (used for both the generator under test and the G-EVAL judge)
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
# G-EVAL scoring (UNCHANGED -- judge is always gpt-4o-mini, independent of GENERATOR_MODEL)
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
# Data loading (UNCHANGED)
# -----------------------------
df_orig = pd.read_csv(ORIGINAL_CSV).fillna("")
if USE_AUGMENTED_TOO and os.path.exists(AUGMENTED_CSV):
    df_aug = pd.read_csv(AUGMENTED_CSV).fillna("")
    df = pd.concat([df_orig, df_aug], ignore_index=True)
else:
    df = df_orig.copy()

df = df.sample(frac=1, random_state=SEED).reset_index(drop=True)

df = df[[COL_PTT, COL_PREV, COL_PREV_RES, COL_STRATEGY, COL_EXPLANATION]].fillna("").head(8)


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


def build_messages(system_prompt: str, user_content: str) -> list:
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]


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
# SINGLE GENERATION (via the OpenAI API instead of a local HF model)
# -----------------------------
def generate_single(messages: list) -> str:
    kwargs = dict(model=GENERATOR_MODEL, messages=messages, max_completion_tokens=MAX_NEW_TOKENS)
    if TEMPERATURE is not None:
        kwargs["temperature"] = TEMPERATURE
    if TOP_P is not None:
        kwargs["top_p"] = TOP_P

    try:
        resp = client.chat.completions.create(**kwargs)
    except Exception as e:
        # Some model tiers (e.g. reasoning-only models) reject non-default
        # temperature/top_p or the max_completion_tokens name entirely.
        # Retry with just model + messages rather than failing the whole run.
        msg = str(e).lower()
        if any(k in msg for k in ("temperature", "top_p", "unsupported", "max_completion_tokens", "max_tokens")):
            resp = client.chat.completions.create(model=GENERATOR_MODEL, messages=messages)
        else:
            raise

    return _content_to_text(getattr(resp.choices[0].message, "content", None))


# -----------------------------
# RUN
# -----------------------------
df["_user_prompt"] = [
    build_user_prompt(ptt, prev, prev_res)
    for ptt, prev, prev_res in zip(df[COL_PTT], df[COL_PREV], df[COL_PREV_RES])
]

df["_messages"] = [build_messages(SYSTEM_PROMPT, u) for u in df["_user_prompt"]]

rows = []

print(f"Generating with {GENERATOR_MODEL} + evaluating...")

for ptt, messages, ref_strat, ref_exp in tqdm(
    zip(df[COL_PTT], df["_messages"], df[COL_STRATEGY], df[COL_EXPLANATION]),
    total=len(df)
):

    gen = generate_single(messages)

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
os.makedirs(os.path.dirname(OUTPUT_CSV) or ".", exist_ok=True)
out_df.to_csv(OUTPUT_CSV, index=False, quoting=csv.QUOTE_ALL, escapechar="\\", encoding="utf-8")

print(f"Saved: {OUTPUT_CSV}")

print("—— Summary ——")
print("Mean strategy similarity:", out_df["similarity_strategy_geval"].mean())
print("Mean explanation similarity:", out_df["similarity_explanation_geval"].mean())
print("Missed strategies:", (out_df["parsed_strategy"] == "").sum())
