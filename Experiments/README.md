# Running the Pen-SLM Experiments

This covers everything under `Experiments/`: the Test-Set evaluations, the
local inference server, and the CTFKnow benchmark. For training the model in
the first place, see the [repo-root README](../README.md).

Set up the environment exactly as in the root README first (venv +
`pip install -r ../requirements.txt` + `export OPENAI_API_KEY=...`).

## Model setup

The trained `Pen-SLM` LoRA adapter is checked into this repo as a Git LFS
archive at `Trained_models/Pen-SLM-LoRA.zip` (no external download needed).
Pull it once before your first run:

```bash
git lfs pull
```

`run_experiments.py` (see below) extracts the zip into `Trained_models/Pen-SLM`
automatically the first time it's needed; you don't need to unzip it by hand.
If `git lfs pull` hasn't been run, the zip on disk is just a small LFS pointer
file, not the real archive -- `run_experiments.py` detects this and tells you
to run `git lfs pull` rather than failing with a confusing zip error.

## Contents

- [Test-Set/](Test-Set/) — GEval-based accuracy checks against held-out pentest
  strategy/action data. `test_strategy_Pen-SLM.py` / `test_action_Pen-SLM.py`
  evaluate the local Pen-SLM adapter; `test_strategy_GPT-5.4.py` /
  `test_action_GPT-5.4.py` run the identical eval against a hosted OpenAI
  model instead, for comparison.
- [server.py](server.py) — loads `Qwen/Qwen3-14B` + the `Trained_models/Pen-SLM`
  LoRA adapter and serves it over FastAPI (custom `/generate` routes plus an
  OpenAI-compatible `/v1/chat/completions`).
- [CTFKnow/](CTFKnow/) — a third-party CTF-knowledge multiple-choice benchmark
  ([paper](CTFKnow/paper.pdf)), vendored in and wired up to run against a
  locally-deployed Pen-SLM.
- [run_experiments.py](run_experiments.py) — orchestrates all of the above:
  extracts the model from the LFS zip if missing, then runs the eval(s) you
  ask for.

## Hardware requirement

`server.py` loads Qwen3-14B in full bf16 by default, which needs roughly
**30-35GB of VRAM** (weights + LoRA + KV cache/activation headroom) — in
practice, **at least a single A100 (40GB or 80GB)** or an equivalent-or-larger
GPU. The same applies to the Test-Set scripts, which load the base model
directly rather than through the server.

**If you don't have an A100-class GPU**, use the 4-bit quantized deployment
instead — this is a real option, not a fallback promise: pass `--quantized`
to `server.py` (or `--quantized-server` to `run_experiments.py`). It loads the
base model in 4-bit (nf4, via `bitsandbytes`), which fits in roughly
**10-12GB of VRAM** and runs on a single consumer GPU (e.g. a 3090/4090),
at some cost to generation quality/latency versus full bf16.

```bash
# full bf16 (needs an A100-class GPU)
python3 Experiments/server.py

# 4-bit quantized (fits on a much smaller GPU)
python3 Experiments/server.py --quantized
```

`--host` / `--port` are also available if you need to bind somewhere other
than `0.0.0.0:8083`. `PEN_SLM_4BIT=1` is equivalent to `--quantized` if you'd
rather set it via environment variable (useful when something else launches
the process for you).

The Test-Set scripts (`test_strategy_Pen-SLM.py`, `test_action_Pen-SLM.py`) do
**not** currently have a quantized option — they call
`AutoModelForCausalLM.from_pretrained(..., torch_dtype=torch.bfloat16)`
directly. If you need to run those on a smaller GPU too, apply the same
`BitsAndBytesConfig` pattern used in `server.py`'s `load_model()`.

## Running things

All commands below assume you're in the repo root with the venv active.

### Test-Set evaluation, against Pen-SLM

```bash
python3 Experiments/run_experiments.py --only strategy   # or --only action, or --only all
```

Extracts `Trained_models/Pen-SLM` from the LFS zip if missing, then runs the
requested Test-Set script(s) against it directly (no server involved). Run
from the repo root — `run_experiments.py` launches these scripts itself with
the right working directory (`Experiments/Test-Set/`); both read
`Data/test_data.csv` and write to `Experiments/Results/`.

### Test-Set evaluation, against a commercial LLM (e.g. GPT-5.4)

`test_strategy_GPT-5.4.py` and `test_action_GPT-5.4.py` run the exact same
eval (same data, prompts, G-EVAL judge) but call a hosted OpenAI model as the
generator instead of loading Pen-SLM locally — no GPU, no `Trained_models/`,
no server needed. They are **not** wired into `run_experiments.py`; run them
directly, with `cwd` set to their own directory (they resolve
`../../Data/test_data.csv` and `../Results/...` relative to themselves):

```bash
export OPENAI_API_KEY=...
cd Experiments/Test-Set
python3 test_strategy_GPT-5.4.py
python3 test_action_GPT-5.4.py
```

Results land in `Experiments/Results/results_GPT-5.4_strategy.csv` and
`Experiments/Results/GPT-5.4_action.csv`.

`"gpt-5.4"` is a placeholder — it's a bare `GENERATOR_MODEL = "gpt-5.4"`
constant near the top of each file, so swap in whatever chat-completions
model id your OpenAI account actually has access to. The G-EVAL judge stays
`gpt-4o-mini` regardless of what you put there, so scores stay comparable
across different generator models (including Pen-SLM's own eval scripts). If
the model rejects `temperature`/`top_p`/`max_completion_tokens` (some
reasoning-tier models only accept defaults), both scripts catch that and
retry with just `model` + `messages` rather than failing the whole run.

### CTFKnow, against a locally-deployed Pen-SLM

```bash
python3 Experiments/run_experiments.py --only ctfknow \
  --ctfknow-questions Experiments/CTFKnow/dataset/question_list.json \
  --quantized-server   # omit this if you have an A100 and want full bf16
```

This launches `server.py` in the background (reusing one already running and
healthy on port 8083, if there is one), waits for the model to finish loading
(`--server-timeout`, default 1800s), runs
`Experiments/CTFKnow/run.py E -M single -l pen-slm -o <questions file>`
against it via the new `/v1/chat/completions` endpoint, then shuts the server
down.

**You need a graded question-list file first** — a JSON list of
`{"question": ..., "answer": "A"}` objects. This repo doesn't ship one;
[CTFKnow/dataset/list_knwoledge_question.json](CTFKnow/dataset/list_knwoledge_question.json)
is knowledge-*extraction* output, not a graded question list. Produce one with
CTFKnow's own pipeline (uses the OpenAI API, separately from Pen-SLM
inference):

```bash
cd Experiments/CTFKnow
python3 run.py K -i dataset/list.json -o dataset/knowledge.json
python3 run.py Q -i dataset/knowledge.json -o dataset/questions.json -q dataset/question_list.json
```

`run_ctfknow` checks the file's shape before starting the server and fails
fast with this same guidance if it's missing or malformed, rather than
crashing after a 14B model has already loaded.

### Deploying the server standalone (no CTFKnow)

Useful for manual testing or pointing any other OpenAI-SDK-compatible tool at
Pen-SLM:

```bash
cd Experiments
python3 server.py --quantized   # drop --quantized if you have an A100
```

Then, from another shell:

```bash
curl http://localhost:8083/health

curl http://localhost:8083/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"pen-slm","messages":[{"role":"user","content":"What is a SQL injection?"}]}'
```

## Notes / gotchas

- `server.py` resolves its LoRA path as `./../Trained_models/Pen-SLM` (relative
  to CWD), so run it with `cwd=Experiments/` — either `cd Experiments &&
  python3 server.py`, or let `run_experiments.py` launch it for you.
- `Qwen/Qwen3-14B` is a "thinking" model and may prepend `<think>...</think>`
  to its output by default. CTFKnow's grading only checks the *first
  character* of the response (`response.choices[0].message.content[0] in
  "ABCD"`), so `/v1/chat/completions` defaults `enable_thinking=False` in the
  chat template to avoid that. Still worth spot-checking a few raw responses
  before trusting the accuracy numbers.
- `run.py`'s `E` command and `Envaluation.envaluate()` had two pre-existing
  bugs (hardcoded model/question-file, and a variable-shadowing bug that made
  every non-Groq model raise `UnboundLocalError`) that were fixed to make the
  `pen-slm` routing possible at all — see the root README's CTFKnow section
  for details.
