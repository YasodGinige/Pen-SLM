# Pen-SLM — Staged GRPO Training

This repo trains a single LoRA adapter on top of **Qwen3-14B** by alternating
between two tasks using GRPO (Group Relative Policy Optimization):

- **Strategy** ([train_strategy_qwen14b.py](train_strategy_qwen14b.py)) — given the
  Penetration Testing Tree (PTT) and the previous step/result, generate the next
  strategy.
- **Action** ([train_action_qwen3_14B.py](train_action_qwen3_14B.py)) — given the PTT
  and a strategy, generate a concrete action plan, MCP server selection, and usage
  instructions.

[staged_training.py](staged_training.py) drives both trainers against one shared
base model + LoRA adapter, switching between them on a schedule
(`SWITCH_INTERVALS = [800, 400, 100, 50, 10]` optimization steps per side, repeating
until `TOTAL_STEPS` is reached).

Both reward pipelines call the OpenAI API (`gpt-4o-mini` by default) as an
LLM-judge, so an `OPENAI_API_KEY` is required even though the base model is local.

For running evaluations and the local inference server after training (sections
9-10 below), see also [Experiments/README.md](Experiments/README.md) for the
full walkthrough, including the 4-bit quantized deployment option for GPUs
smaller than an A100.

## 1. Requirements

- Linux with an NVIDIA H100 GPU (bitsandbytes 8-bit optimizer + bf16 training). A 14B
  model with LoRA + gradient checkpointing comfortably needs **≥48GB VRAM**;
  reduce `per_device_train_batch_size` in the trainer files if you have less.
- Python 3.10–3.12 (Qwen3 tokenizer/model support requires a recent
  `transformers`; very new Python versions may lag behind `bitsandbytes` /
  `torch` wheel availability).
- An OpenAI API key with access to `gpt-4o-mini`.

## 2. Create the virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
```

## 3. Install dependencies

A [requirements.txt](requirements.txt) is included in this repo.

```bash
pip install -r requirements.txt
```

If your CUDA version needs a specific PyTorch build, install `torch` first
from the [official index](https://pytorch.org/get-started/locally/) matching
your CUDA version, then run the `pip install -r requirements.txt` above (pip
will skip the already-satisfied `torch`).

## 4. Set your OpenAI API key

```bash
export OPENAI_API_KEY="sk-..."
```

Both `train_strategy_qwen14b.py` and `train_action_qwen3_14B.py` read this
from the environment; `train_action_qwen3_14B.py` will raise immediately at
import time if it's missing.

## 5. Data

Training data lives in [Data/training_data.csv](Data/training_data.csv) and
must contain (at least) these columns:

```
PTT, Previous step, Previous step result, New strategy, Strategy explanation,
Action, MCP servers, MCP server usage
```

- The strategy dataset uses `PTT`, `Previous step`, `Previous step result` →
  `New strategy` (+ `Strategy explanation`).
- The action dataset uses `PTT`, `New strategy`, `Strategy explanation` →
  `Action`, `MCP servers`, `MCP server usage`.

## 6. Working directory (important)

The training scripts load data and write checkpoints using paths relative to
**one directory below the repo root**:

```python
pd.read_csv('./../Data/training_data.csv')
FINAL_OUTPUT_DIR = "./../Trained_models/staged_final"
```

So you must run the training command from a subdirectory of the repo (not
the repo root itself), so that `../Data` resolves back to
[Data/](Data). Create one and run from there, e.g.:

```bash
mkdir -p run
cd run
python3 ../staged_training.py
```

This will create `Trained_models/` as a sibling of `Data/` and `Experiments/`
at the repo root.

## 7. Run staged training

From the `run/` directory created above:

```bash
python3 ../staged_training.py \
  --total-steps 4000 \
  --start-task strategy
```

Options ([staged_training.py](staged_training.py)):

- `--total-steps`: total optimization steps across the whole staged run
  (default `4000`).
- `--start-task {strategy,action}`: which task runs first in each paired stage
  (default `strategy`).
- `--strategy-part` / `--action-part`: optional fixed dataset slice/row-count
  for each task (e.g. `slice(0,1000)` or `500`). If both are left unset, the
  script cycles through the dataset in a shared, wrapping row window so both
  tasks train on matching examples.

The run prints progress per stage (`Finished paired stage: X/TOTAL_STEPS steps
completed`) and saves LoRA checkpoints under `Trained_models/staged_final/`.
By default `staged_training.py` resumes from
`Trained_models/staged_final/checkpoint-strategy_800`
(`lora_adapter_path` in [staged_training.py](staged_training.py:16)) — for a
fresh run with no prior adapter, edit that path to `None` before starting.

## 8. Monitoring

Training logs (loss, reward components) print to stdout every step
(`logging_steps = 1`); no external experiment tracker is wired up
(`report_to = "none"` in both trainer configs).

## 9. Run evaluation experiments

[Experiments/run_experiments.py](Experiments/run_experiments.py) fetches the
trained `Pen-SLM` LoRA adapter into `Trained_models/Pen-SLM` (downloading it
from Google Drive via `gdown` if it isn't there yet) and then runs both
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

Requires `OPENAI_API_KEY` to be set (both eval scripts use `gpt-4o-mini` as an
LLM judge, same as training).

**Known gaps you'll need to resolve before this produces results:**

- `test_action_Pen-SLM.py` hardcodes its adapter path as
  `Trained_models/GRPO_Qwen14B_single/checkpoint-final`, a different name than
  the downloaded `Pen-SLM` model. `run_experiments.py` works around this by
  symlinking that path to `Trained_models/Pen-SLM` rather than editing the
  eval script.
- Both eval scripts expect test CSVs that don't currently exist in
  [Data/](Data): `Data/processed_data_test.csv` (+ optional
  `Data/test_claude.csv`) for the strategy script, and
  `Data/output_test_data.csv` for the action script. `Data/test_data.csv` has
  a matching column schema (`Machine, PTT, Previous strategy, Previous step,
  Previous step result, New strategy, Strategy explanation, Action, MCP
  servers, MCP server usage, Results`) and looks like the intended source —
  `run_experiments.py` will not guess for you, it just skips a script and
  tells you which file is missing.
- [test_strategy_Pen-SLM.py:33](Experiments/Test-Set/test_strategy_Pen-SLM.py:33)
  loads `Qwen/Qwen3-8B` as the base model while every other script in this
  repo trains/evaluates against `Qwen/Qwen3-14B`. If the downloaded adapter
  was trained on the 14B base, loading it onto the 8B base will fail (or
  silently mismatch) — verify which base the adapter expects before trusting
  the strategy results.

## 10. Run the CTFKnow benchmark against a locally-deployed Pen-SLM

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

## Notes / gotchas

- `staged_training.py` imports `train_action_qwen3_14B` and
  `train_strategy_qwen14b` as plain Python modules — both files must sit next
  to `staged_training.py` with those exact names (no spaces or suffixes).
- OpenAI calls are rate-limited client-side (`RPM = 15`, `MAX_CONCURRENCY = 8`
  in both trainer files) — raise these to match your actual OpenAI quota if
  training is judge-bottlenecked.
