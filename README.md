# Pen-SLM — A Small Language Model for Automated Penetration Testing

Pen-SLM fine-tunes **Qwen3-14B** with a shared LoRA adapter using **GRPO** for two penetration-testing tasks:

* **Strategy generation** — predicts the next high-level strategy from the Penetration Testing Tree (PTT) and previous results.
* **Action planning** — converts a strategy into a concrete action plan, including MCP server selection and usage.

The two tasks are trained alternately using [`staged_training.py`](staged_training.py).

## Requirements

* Linux with an NVIDIA GPU
* **48 GB+ VRAM recommended** (e.g., NVIDIA H100)
* Python 3.10–3.12
* OpenAI API key

The OpenAI API is used as an LLM judge during training.

## Installation

```bash
git clone <repository-url>
cd <repository>

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

Set your OpenAI API key:

```bash
export OPENAI_API_KEY="your-api-key"
```

## Training Data

Training data is provided in [`Data/training_data.csv`](Data/training_data.csv).

The dataset contains the following columns:

```text
PTT
Previous step
Previous step result
New strategy
Strategy explanation
Action
MCP servers
MCP server usage
```

The strategy task uses the PTT and previous step information to predict the **new strategy** and its explanation.

The action task uses the strategy and its explanation to predict the **action plan**, MCP servers, and their usage.

## Training

Run the training script from a subdirectory of the repository:

```bash
mkdir -p run
cd run

python3 ../staged_training.py \
    --total-steps 4000 \
    --start-task strategy
```

The training alternates between strategy and action planning and saves the resulting LoRA checkpoints to:

```text
Trained_models/Pen-SLM/
```

### Options

```text
--total-steps     Total training steps (default: 4000)
--start-task      First task: strategy or action
```

For evaluation and local inference, see [`Experiments/README.md`](Experiments/README.md).


## 8. Run evaluation experiments

[Experiments/run_experiments.py](Experiments/run_experiments.py) fetches the
trained `Pen-SLM` LoRA adapter into `Trained_models/Pen-SLM` and then runs both
scripts in [Experiments/Test-Set](Experiments/Test-Set):
[test_strategy_Pen-SLM.py](Experiments/Test-Set/test_strategy_Pen-SLM.py) and
[test_action_Pen-SLM.py](Experiments/Test-Set/test_action_Pen-SLM.py).

Run it from the repo root (unlike `staged_training.py`, this one expects to
be launched from the repo root, not a subdirectory):

```bash
python3 Experiments/run_experiments.py
```

- `--force-download` re-downloads the model even if `Trained_models/Pen-SLM`
  already looks populated.
- `--only strategy` / `--only action` runs just one of the two eval scripts.

Requires `OPENAI_API_KEY` to be set (both eval scripts use `gpt-4o` as an
LLM judge, same as training).


## 9. Run the CTFKnow benchmark against a locally-deployed Pen-SLM

[Experiments/server.py](Experiments/server.py) loads the base `Qwen/Qwen3-14B`
model + the `Trained_models/Pen-SLM` LoRA adapter and serves it over FastAPI,
including an OpenAI-compatible `POST /v1/chat/completions` endpoint (added
alongside the original `/generate` / `/batch_generate` routes) so external
tools that speak the OpenAI SDK can target it via `base_url`.
[Experiments/CTFKnow](Experiments/CTFKnow/) — a third-party CTF-knowledge MCQ
benchmark vendored into this repo — is one such tool.

**Hardware:** full bf16 inference of Qwen3-14B needs ~30-35GB VRAM, i.e. **at
least an A100-class GPU**. If you don't have one, pass `--quantized` to
`server.py` (or `--quantized-server` below) to load the base model in 4-bit
via `bitsandbytes` instead (~10-12GB VRAM, some quality/speed tradeoff). See
[Experiments/README.md](Experiments/README.md) for details.

`run_experiments.py` wires the two together:

```bash
python3 Experiments/run_experiments.py --only ctfknow \
  --ctfknow-questions Experiments/CTFKnow/dataset/question_list.json
```

This will: ensure `Trained_models/Pen-SLM` is downloaded, launch
`Experiments/server.py` in the background (or reuse one already running and
healthy on port 8083), poll `/health` until the model finishes loading
(`--server-timeout`, default 1800s), run
`Experiments/CTFKnow/run.py E -M single -l pen-slm -o <questions file>`
against it, then shut the server down.

**Before this can run, you need a graded question-list file** — a JSON list
of `{"question": ..., "answer": "A"}`-shaped objects. This repo doesn't ship
one: [dataset/list_knwoledge_question.json](Experiments/CTFKnow/dataset/list_knwoledge_question.json)
is CTFKnow's *knowledge-extraction* output (no `question`/`answer` fields),
not the graded question list its own README describes producing via:

```bash
cd Experiments/CTFKnow
python3 run.py K -i dataset/list.json -o dataset/knowledge.json
python3 run.py Q -i dataset/knowledge.json -o dataset/questions.json -q dataset/question_list.json
```

(`K`/`Q` call the OpenAI API — `gpt-3.5-turbo`/`gpt-4-0125-preview` — so budget
for that separately from the local Pen-SLM inference.) `run_ctfknow` checks
the file's shape up front and fails fast with this same guidance rather than
crashing after the model has already loaded.

Fixes made to [Experiments/CTFKnow/run.py](Experiments/CTFKnow/run.py) to
make this work at all (both were pre-existing bugs, not something introduced
by the Pen-SLM integration):

- `main()`'s `E` command ignored `--llm`/`--output` and always evaluated the
  hardcoded model `mistralai/mixtral-8x7b-instruct-v0.1` against a
  hardcoded, non-existent `dataset/question_log_mix.json`. It now uses
  `args.llm` / `args.output` (the latter doubles as both the input question
  list and where graded results get written back, matching how `Envaluation`
  already behaved).
- `Envaluation.envaluate()` assigned to a local variable named `client` only
  inside its Groq branch, which under Python's scoping rules made `client`
  local to the whole method — so any non-Groq model (i.e. everything except
  two hardcoded Groq model names) hit `UnboundLocalError` before this fix.
  It's renamed to `chat_client`, with a new branch that routes `-l pen-slm`
  (or `pen-slm-local`) to the local server via
  `OpenAI(base_url=os.environ.get("PEN_SLM_SERVER_URL", "http://localhost:8083/v1"))`.

Also note: `Qwen/Qwen3-14B` is a "thinking" model that may prepend
`<think>...</think>` to its output by default; CTFKnow's grading only checks
`response.choices[0].message.content[0] in "ABCD"`. The `/v1/chat/completions`
endpoint defaults `enable_thinking=False` in the chat template specifically
to avoid this, but verify the adapter actually answers with a bare letter as
its system prompt asks before trusting the accuracy numbers.


