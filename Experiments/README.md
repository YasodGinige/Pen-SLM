# Running the Pen-SLM Experiments

This covers everything under `Experiments/`: the Test-Set evaluations, the
local inference server, and the CTFKnow benchmark. For training the model in
the first place, see the [repo-root README](../README.md).

Set up the environment exactly as in the root README first (venv +
`pip install -r ../requirements.txt` + `export OPENAI_API_KEY=...`).

## Contents

- [Test-Set/](Test-Set/) — `test_strategy_Pen-SLM.py` and `test_action_Pen-SLM.py`,
  GEval-based accuracy checks against held-out pentest strategy/action data.
- [server.py](server.py) — loads `Qwen/Qwen3-14B` + the `Trained_models/Pen-SLM`
  LoRA adapter and serves it over FastAPI (custom `/generate` routes plus an
  OpenAI-compatible `/v1/chat/completions`).
- [CTFKnow/](CTFKnow/) — a third-party CTF-knowledge multiple-choice benchmark
  ([paper](CTFKnow/paper.pdf)), vendored in and wired up to run against a
  locally-deployed Pen-SLM.
- [run_experiments.py](run_experiments.py) — orchestrates all of the above:
  downloads the model if missing, then runs the eval(s) you ask for.

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

### Test-Set evaluation

```bash
python3 Experiments/run_experiments.py --only strategy   # or --only action, or --only all
```

Downloads `Trained_models/Pen-SLM` if missing, then runs the requested
Test-Set script(s) directly against the base model (no server involved).
See the root README's "Run evaluation experiments" section for the data-file
caveats (some CSVs these scripts expect aren't included in this repo).

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
