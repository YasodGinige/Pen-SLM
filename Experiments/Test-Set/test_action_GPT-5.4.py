# -*- coding: utf-8 -*-
"""
Same action-generation eval as test_action_Pen-SLM.py, but with GPT-5.4
(a hosted OpenAI model) as the generator under test instead of the local
Qwen3-14B + Pen-SLM LoRA adapter. Runs inference on output_test_data.csv and
scores each sample with:

  1. Action GEval       — 3 criteria [0,1] each, averaged
       • Task alignment
       • Tool alignment
       • End goal alignment

  2. MCP Server Accuracy — exact set match per sample, averaged across dataset

  3. MCP Usage GEval    — 2 criteria [0,1] each, averaged per sample
       • Action alignment
       • End goal alignment

Judge model: gpt-4o-mini (independent of GENERATOR_MODEL, set OPENAI_API_KEY
in environment)

Requirements:
    pip install pandas numpy openai tqdm nest_asyncio
"""
import os, re, json, asyncio, random
from typing import List, Dict, Set, Optional

import numpy as np
import pandas as pd
from tqdm import tqdm

from openai import OpenAI, AsyncOpenAI
import nest_asyncio

# ─────────────────────────── Config ────────────────────────────────────────
# Model under test. Adjust this if "gpt-5.4" isn't the exact model id your
# OpenAI account has access to -- everything else in this script is agnostic
# to which chat-completions-compatible model id you put here.
GENERATOR_MODEL = "gpt-5.4"

TEST_CSV        = "./../../Data/test_data.csv"
OUTPUT_CSV      = "./../Results/GPT-5.4_action.csv"

JUDGE_MODEL     = "gpt-4o-mini"   # G-EVAL judge model, independent of GENERATOR_MODEL
RPM             = 15
MAX_CONCURRENCY = 8
TIMEOUT_S       = 60

MAX_NEW_TOKENS  = 2048
TEMPERATURE     = 0.0   # deterministic inference (falls back to model default if unsupported)

SEED = 2187
np.random.seed(SEED)
random.seed(SEED)

# ─────────────────────────── Approved servers ──────────────────────────────
APPROVED_SERVERS: Set[str] = {
    "Nmap", "Metasploit", "Netcat", "Dirbuster", "SQLmap", "SMB Client",
    "Hydra", "Burp Suite", "Hashcat", "Google Search", "File System Analysis",
    "ExploitDB", "Interactive CLI", "Web Page Analysis",
}
APPROVED_LIST_STR = ", ".join(sorted(APPROVED_SERVERS))

# ─────────────────────────── Regex patterns ────────────────────────────────
RE_THINK       = re.compile(r"<think>(.*?)</think>",             re.DOTALL)
RE_ACTION      = re.compile(r"<action>(.*?)</action>",           re.DOTALL)
RE_MCP_SERVERS = re.compile(r"<mcp_servers>(.*?)</mcp_servers>", re.DOTALL)
RE_MCP_USAGE   = re.compile(r"<mcp_usage>(.*?)</mcp_usage>",     re.DOTALL)

# ─────────────────────────── Parsing helpers ───────────────────────────────
def _extract_sections(text: str) -> Dict[str, str]:
    return {
        "think":       (m.group(1).strip() if (m := RE_THINK.search(text))       else ""),
        "action":      (m.group(1).strip() if (m := RE_ACTION.search(text))      else ""),
        "mcp_servers": (m.group(1).strip() if (m := RE_MCP_SERVERS.search(text)) else ""),
        "mcp_usage":   (m.group(1).strip() if (m := RE_MCP_USAGE.search(text))   else ""),
    }


def _parse_server_list(raw: str) -> List[str]:
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

# ─────────────────────────── Generator (model under test) ──────────────────
gen_client = OpenAI()


def generate_with_gpt(messages: list) -> str:
    kwargs = dict(model=GENERATOR_MODEL, messages=messages, max_completion_tokens=MAX_NEW_TOKENS)
    if TEMPERATURE is not None:
        kwargs["temperature"] = TEMPERATURE

    try:
        resp = gen_client.chat.completions.create(**kwargs)
    except Exception as e:
        # Some model tiers (e.g. reasoning-only models) reject non-default
        # temperature or the max_completion_tokens name entirely. Retry with
        # just model + messages rather than failing the whole run.
        msg = str(e).lower()
        if any(k in msg for k in ("temperature", "unsupported", "max_completion_tokens", "max_tokens")):
            resp = gen_client.chat.completions.create(model=GENERATOR_MODEL, messages=messages)
        else:
            raise

    content = resp.choices[0].message.content
    return content if isinstance(content, str) else str(content or "")

# ─────────────────────────── OpenAI async helpers (G-EVAL judge only) ──────
_client = AsyncOpenAI()


async def _sleep_for_rate_limit():
    base = 60.0 / max(1, RPM)
    await asyncio.sleep(random.uniform(0.0, base / 5))


async def _chat_once(prompt: str, max_retries: int = 5) -> str:
    delay = 1.0
    for attempt in range(1, max_retries + 1):
        try:
            resp = await _client.chat.completions.create(
                model=JUDGE_MODEL,
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


def _parse_score_01(text: str) -> float:
    """Parse a JSON score expected in [0, 1]. Returns 0.0 on failure."""
    try:
        return float(json.loads((text or "").strip()).get("score", 0.0))
    except Exception:
        # fallback: look for a bare float
        m = re.search(r"\b(0(\.\d+)?|1(\.0+)?)\b", text or "")
        return float(m.group()) if m else 0.0

# ─────────────────────────── GEval prompt builders ─────────────────────────
def _prompt_action_task_alignment(strategy: str, explanation: str, ground_truth: str, generated: str) -> str:
    return f"""
You are an expert evaluator assessing a penetration testing action plan.

Strategy: {strategy}
Strategy explanation: {explanation}

Criterion — Task Alignment:
Does the generated action plan address the same penetration testing task as described in the strategy and strategy explanation?
Does it focus on the correct target, service, or vulnerability class?

Score 0.0 = completely unrelated to the task
Score 0.5 = partially aligned, some relevant steps but misses key objectives
Score 1.0 = fully aligned, all steps directly serve the task

Return ONLY JSON: {{"score": <float in [0.0, 1.0]>, "explanation": "<one sentence>"}}

GROUND TRUTH ACTION:
{ground_truth}

GENERATED ACTION:
{generated}
""".strip()


def _prompt_action_tool_alignment(strategy: str, gt_servers: str, ground_truth: str, generated: str) -> str:
    return f"""
You are an expert evaluator assessing a penetration testing action plan.

Strategy: {strategy}
Ground truth MCP Servers (tools): {gt_servers}

Criterion — Tool Alignment:
Compare the generated action plan to the ground truth action plan.
Does the generated plan align with and make sensible use of the same MCP servers as the ground truth?
Are the action steps consistent with what those tools can actually do?

Score 0.0 = actions are incompatible with or ignore the ground truth tools entirely
Score 0.5 = partially aligned, some steps fit the tools but others do not match the ground truth approach
Score 1.0 = fully aligned, every action step maps naturally to the ground truth tool selection

Return ONLY JSON: {{"score": <float in [0.0, 1.0]>, "explanation": "<one sentence>"}}

GROUND TRUTH ACTION:
{ground_truth}

GENERATED ACTION:
{generated}
""".strip()


def _prompt_action_goal_alignment(strategy: str, explanation: str, ground_truth: str, generated: str) -> str:
    return f"""
You are an expert evaluator assessing a penetration testing action plan.

Strategy: {strategy}
Strategy explanation: {explanation}

Criterion — End Goal Alignment:
Does the generated action plan lead toward the same ultimate penetration testing objective (e.g., gaining access, privilege escalation, data exfiltration, lateral movement) as the ground truth?
Would executing this plan bring a tester meaningfully closer to the final goal?

Score 0.0 = completely misses the end goal
Score 0.5 = partially moves toward the goal but lacks key steps or goes in a wrong direction
Score 1.0 = fully aligned with the end goal, effectively achieves the intended outcome

Return ONLY JSON: {{"score": <float in [0.0, 1.0]>, "explanation": "<one sentence>"}}

GROUND TRUTH ACTION:
{ground_truth}

GENERATED ACTION:
{generated}
""".strip()


def _prompt_usage_action_alignment(server: str, gt_action: str, gt_usage: str, generated_usage: str) -> str:
    return f"""
You are an expert evaluator assessing MCP server usage instructions for a penetration testing step.

Server: {server}

Criterion — Action Alignment:
Compare the generated usage description to the ground truth usage description.
Does the generated usage align with and support the ground truth action plan steps?
Are the server instructions consistent with what the ground truth action plan calls for?

Score 0.0 = generated usage is completely inconsistent with the ground truth action plan
Score 0.5 = partially consistent, some overlap but key action steps are not reflected
Score 1.0 = fully consistent, generated usage clearly supports every relevant step in the ground truth action plan

Return ONLY JSON: {{"score": <float in [0.0, 1.0]>, "explanation": "<one sentence>"}}

GROUND TRUTH ACTION PLAN:
{gt_action}

GROUND TRUTH USAGE FOR {server}:
{gt_usage}

GENERATED USAGE FOR {server}:
{generated_usage}
""".strip()


def _prompt_usage_goal_alignment(server: str, strategy: str, explanation: str,
                                 gt_usage: str, generated_usage: str) -> str:
    return f"""
You are an expert evaluator assessing MCP server usage instructions for a penetration testing step.

Server: {server}
Strategy: {strategy}
Strategy explanation: {explanation}

Criterion — End Goal Alignment:
Compare the generated usage description to the ground truth usage description.
Does the generated usage target the same end goal as the ground truth?
Does it specify expected findings or results that match what the ground truth says should be achieved?

Score 0.0 = generated usage has no connection to the ground truth end goal
Score 0.5 = partially aligned, mentions the goal but findings/expected results diverge from the ground truth
Score 1.0 = fully aligned, generated usage describes the same expected outcome as the ground truth

Return ONLY JSON: {{"score": <float in [0.0, 1.0]>, "explanation": "<one sentence>"}}

GROUND TRUTH USAGE FOR {server}:
{gt_usage}

GENERATED USAGE FOR {server}:
{generated_usage}
""".strip()

# ─────────────────────────── Per-sample evaluation ─────────────────────────
def evaluate_action(strategy: str, explanation: str, gt_action: str, gt_servers_str: str,
                    gen_action: str) -> Dict[str, float]:
    """Run 3-criterion GEval for the Action section. Returns scores in [0,1]."""
    prompts = [
        _prompt_action_task_alignment(strategy, explanation, gt_action, gen_action),
        _prompt_action_tool_alignment(strategy, gt_servers_str, gt_action, gen_action),
        _prompt_action_goal_alignment(strategy, explanation, gt_action, gen_action),
    ]
    responses = _run_async(_chat_batch(prompts))
    task_score, tool_score, goal_score = [_parse_score_01(r) for r in responses]
    return {
        "action_task_alignment":  task_score,
        "action_tool_alignment":  tool_score,
        "action_goal_alignment":  goal_score,
        "action_score":           round((task_score + tool_score + goal_score) / 3.0, 4),
    }


def evaluate_mcp_servers(gt_servers_str: str, gen_servers_str: str) -> Dict[str, object]:
    """Precision: fraction of predicted servers that appear in the ground truth."""
    gt_set  = set(s for s in _parse_server_list(gt_servers_str)  if s in APPROVED_SERVERS)
    gen_set = set(s for s in _parse_server_list(gen_servers_str) if s in APPROVED_SERVERS)
    correct = gt_set & gen_set
    precision = len(correct) / len(gen_set) if gen_set else 0.0
    return {
        "mcp_gt":          sorted(gt_set),
        "mcp_predicted":   sorted(gen_set),
        "mcp_correct":     sorted(correct),
        "mcp_accuracy":    round(precision, 4),
    }


def evaluate_mcp_usage(strategy: str, explanation: str, gt_servers_str: str,
                       gen_servers_str: str, gt_action: str, gt_usage_text: str,
                       gen_usage_text: str) -> Dict[str, float]:
    """Run 2-criterion GEval for MCP usage, only for correctly predicted servers."""
    gt_set  = set(s for s in _parse_server_list(gt_servers_str)  if s in APPROVED_SERVERS)
    gen_set = set(s for s in _parse_server_list(gen_servers_str) if s in APPROVED_SERVERS)
    correct_servers = sorted(gt_set & gen_set)

    gt_blocks  = _parse_usage_blocks(gt_usage_text)
    gen_blocks = _parse_usage_blocks(gen_usage_text)

    if not correct_servers:
        return {"usage_action_alignment": 0.0, "usage_goal_alignment": 0.0, "usage_score": 0.0}

    prompts: List[str] = []
    for server in correct_servers:
        gen_block = gen_blocks.get(server, "")
        gt_block  = gt_blocks.get(server, "")
        prompts.append(_prompt_usage_action_alignment(server, gt_action, gt_block, gen_block))
        prompts.append(_prompt_usage_goal_alignment(server, strategy, explanation, gt_block, gen_block))

    responses = _run_async(_chat_batch(prompts))

    action_scores, goal_scores = [], []
    for i in range(len(correct_servers)):
        action_scores.append(_parse_score_01(responses[2 * i]))
        goal_scores.append(_parse_score_01(responses[2 * i + 1]))

    avg_action = float(np.mean(action_scores))
    avg_goal   = float(np.mean(goal_scores))
    return {
        "usage_action_alignment": round(avg_action, 4),
        "usage_goal_alignment":   round(avg_goal, 4),
        "usage_score":            round((avg_action + avg_goal) / 2.0, 4),
    }

# ─────────────────────────── System prompt ─────────────────────────────────
SYSTEM_PROMPT = (
    "You are a penetration testing action planner. "
    "Given the current PTT (Penetration Testing Tree), a new strategy, and its explanation, "
    "generate a concrete action plan, select the minimum required MCP servers, "
    "and explain how to use each one.\n\n"
    f"Available MCP servers: {APPROVED_LIST_STR}\n\n"
    "Output format (use these exact tags):\n"
    "<think>brief logical reasoning (≤512 tokens)</think>\n"
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

# ─────────────────────────── Prompt building ────────────────────────────────
def build_prompt(ptt: str, strategy: str, explanation: str) -> list:
    user_text = (
        f"<PTT>{ptt}</PTT>\n"
        f"<New strategy>{strategy}</New strategy>\n"
        f"<Strategy explanation>{explanation}</Strategy explanation>\n\n"
        "Generate the action plan, MCP servers, and usage instructions for this penetration testing step.\n"
        "Use the exact output format specified in the system prompt."
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": user_text},
    ]

# ─────────────────────────── Main evaluation loop ──────────────────────────
def main():
    if not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY environment variable not set.")

    # Load test data
    df = pd.read_csv(TEST_CSV).fillna("").astype(str).map(str.strip)
    print(f"Loaded {len(df)} test samples from {TEST_CSV}")
    print(f"Generator under test: {GENERATOR_MODEL}  |  Judge: {JUDGE_MODEL}")

    results = []

    for idx, row in tqdm(df.iterrows(), total=len(df), desc="Evaluating"):
        ptt         = row.get("PTT", "")
        strategy    = row.get("New strategy", "")
        explanation = row.get("Strategy explanation", "")
        gt_action   = row.get("Action", "")
        gt_servers  = row.get("MCP servers", "")
        gt_usage    = row.get("MCP server usage", "")

        # ── Inference ──────────────────────────────────────────────────────
        messages   = build_prompt(ptt, strategy, explanation)
        raw_output = generate_with_gpt(messages)
        sections   = _extract_sections(raw_output)

        gen_action   = sections["action"]
        gen_servers  = sections["mcp_servers"]
        gen_usage    = sections["mcp_usage"]

        print('\n\n\n\n---------------------------------\n\n')
        print('gen_action:',gen_action)
        print('\ngen_servers:',gen_servers)
        print('\ngen_usage:',gen_usage)
        print('\n\n---------------------------------\n\n')

        # ── Metric 1: Action GEval ─────────────────────────────────────────
        action_scores = evaluate_action(
            strategy, explanation, gt_action, gt_servers, gen_action
        )

        # ── Metric 2: MCP Server Accuracy ─────────────────────────────────
        mcp_scores = evaluate_mcp_servers(gt_servers, gen_servers)

        # ── Metric 3: MCP Usage GEval ─────────────────────────────────────
        usage_scores = evaluate_mcp_usage(
            strategy, explanation, gt_servers, gen_servers, gt_action, gt_usage, gen_usage
        )

        record = {
            # original columns
            "Machine":            row.get("Machine", ""),
            "PTT":                ptt,
            "Previous strategy":  row.get("Previous strategy", ""),
            "Previous step":      row.get("Previous step", ""),
            "Previous step result": row.get("Previous step result", ""),
            "New strategy":       strategy,
            "Strategy explanation": explanation,
            # ground truth
            "gt_Action":          gt_action,
            "gt_MCP_servers":     gt_servers,
            "gt_MCP_usage":       gt_usage,
            # generated
            "gen_raw_output":     raw_output,
            "gen_Action":         gen_action,
            "gen_MCP_servers":    gen_servers,
            "gen_MCP_usage":      gen_usage,
            # scores
            **action_scores,
            **mcp_scores,
            **usage_scores,
        }
        results.append(record)

        # Progress update after every 10 samples
        if (idx + 1) % 10 == 0:
            so_far = pd.DataFrame(results)
            print(
                f"\n[{idx+1}/{len(df)}]  "
                f"action_score={so_far['action_score'].mean():.3f}  "
                f"mcp_accuracy={so_far['mcp_accuracy'].mean():.3f}  "
                f"usage_score={so_far['usage_score'].mean():.3f}"
            )

    # ── Save results ───────────────────────────────────────────────────────
    results_df = pd.DataFrame(results)
    os.makedirs(os.path.dirname(OUTPUT_CSV) or ".", exist_ok=True)
    results_df.to_csv(OUTPUT_CSV, index=False)
    print(f"\nResults saved to {OUTPUT_CSV}")

    # ── Aggregate metrics ──────────────────────────────────────────────────
    print("\n" + "=" * 55)
    print("AGGREGATE EVALUATION RESULTS")
    print("=" * 55)

    n = len(results_df)

    # Action
    print(f"\nAction GEval  (n={n})")
    print(f"  Task alignment : {results_df['action_task_alignment'].mean():.4f}")
    print(f"  Tool alignment : {results_df['action_tool_alignment'].mean():.4f}")
    print(f"  Goal alignment : {results_df['action_goal_alignment'].mean():.4f}")
    print(f"  Overall        : {results_df['action_score'].mean():.4f}")

    # MCP Servers
    print(f"\nMCP Server Accuracy  (n={n})")
    print(f"  Precision      : {results_df['mcp_accuracy'].mean():.4f}")

    # MCP Usage
    print(f"\nMCP Usage GEval  (n={n})")
    print(f"  Action align   : {results_df['usage_action_alignment'].mean():.4f}")
    print(f"  Goal align     : {results_df['usage_goal_alignment'].mean():.4f}")
    print(f"  Overall        : {results_df['usage_score'].mean():.4f}")

    print("\n" + "=" * 55)


if __name__ == "__main__":
    main()
