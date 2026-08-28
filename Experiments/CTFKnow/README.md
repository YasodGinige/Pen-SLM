# CTFKnow (Pen-SLM integration)

[CTFKnow](paper.pdf) is a third-party CTF-knowledge multiple-choice benchmark,
vendored into this repo. This README covers only what's needed to set it up
and run it against **Pen-SLM** (this repo's locally-deployed fine-tuned model)
and against a **commercial LLM** such as `gpt-5-mini` (via the OpenAI API), for
comparison. For CTFKnow's own general documentation see [README-new.md](README-new.md).

## 1. Prerequisites

- From the repo root: venv + `pip install -r ../../requirements.txt` (installs
  `openai`, `replicate`, `matplotlib`, and everything else `run.py` imports).
- `export OPENAI_API_KEY=...` — **required even when evaluating Pen-SLM.**
  `run.py` constructs an OpenAI client unconditionally at import time
  (`client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])`), and the `K`/`Q`
  steps below call the OpenAI API directly.

## 2. Get a graded question-list file

This repo doesn't ship one. [dataset/list_knwoledge_question.json](dataset/list_knwoledge_question.json)
is CTFKnow's *knowledge-extraction* output (no `question`/`answer` fields) —
not something you can evaluate against. Produce a real question list first:

```bash
cd Experiments/CTFKnow
python3 run.py K -i dataset/list.json -o dataset/knowledge.json
python3 run.py Q -i dataset/knowledge.json -o dataset/questions.json -q dataset/question_list.json
```

`K` and `Q` call the OpenAI API (`gpt-3.5-turbo` / `gpt-4-0125-preview`) to
extract knowledge and generate multiple-choice questions from the write-ups
under `dataset/raw/`. This produces `dataset/question_list.json` — a JSON list
of `{"question": ..., "answer": "A"}` objects — which is what you pass to `-o`
in the evaluation step below (`Envaluation` reads it as input and writes
graded results back into the same file).

## 3. Run with Pen-SLM (local)

Pen-SLM is served locally via [Experiments/server.py](../server.py), which
exposes an OpenAI-compatible `/v1/chat/completions` endpoint. `run.py`
recognizes the model name `pen-slm` and routes it there automatically.

**Easiest path** — from the repo root, this extracts the model if needed,
starts the server, waits for it to load, runs the evaluation, and shuts the
server down:

```bash
python3 Experiments/run_experiments.py --only ctfknow \
  --ctfknow-questions Experiments/CTFKnow/dataset/question_list.json
# add --quantized-server if you don't have an A100-class GPU
```

**Manual path**, if you want the server running independently. From the repo
root, one-time model setup:

```bash
git lfs pull
python3 -c "import sys; sys.path.insert(0, 'Experiments'); import run_experiments as r; r.ensure_model_available()"
```

Then, in one terminal, start the server and leave it running (`server.py`
blocks in the foreground):

```bash
cd Experiments && python3 server.py            # or: python3 server.py --quantized
```

In a second terminal, once `curl http://localhost:8083/health` reports
`model_loaded: true`, run the evaluation against it:

```bash
cd Experiments/CTFKnow
python3 run.py E -M single -l pen-slm -o dataset/question_list.json
```

If the server isn't on the default `http://localhost:8083`, set
`PEN_SLM_SERVER_URL` (e.g. `export PEN_SLM_SERVER_URL=http://localhost:8083/v1`)
before running `run.py`.

**Note:** Qwen3-14B is a "thinking" model and may prepend `<think>...</think>`
to its output by default. CTFKnow's grading only checks the *first character*
of the response (`response.choices[0].message.content[0] in "ABCD"`), so the
`/v1/chat/completions` endpoint defaults `enable_thinking=False` to avoid
this — worth spot-checking a few raw responses before trusting the accuracy
numbers.

## 4. Run with a commercial LLM (e.g. `gpt-5-mini`)

No local server needed — any model your `OPENAI_API_KEY` has access to works
directly through `-l`:

```bash
cd Experiments/CTFKnow
python3 run.py E -M single -l gpt-5-mini -o dataset/question_list.json
```

Swap `gpt-5-mini` for whatever model id you want to benchmark. Since `-o` is
read as input too, copy the ungraded question list first if you want a
separate graded file per model instead of overwriting the same one:

```bash
cp dataset/question_list.json dataset/question_list_gpt5mini.json
python3 run.py E -M single -l gpt-5-mini -o dataset/question_list_gpt5mini.json
```

## 5. Results

`-o` doubles as both input and output: `Envaluation` reads the question list
from it and writes each question's grade (`correct` / `incorrect` /
`undesired`, keyed by model name) back into the same file as it goes. A final
`correct=.. incorrect=.. undesired=..` summary for the run prints to stdout
once all questions are graded.
