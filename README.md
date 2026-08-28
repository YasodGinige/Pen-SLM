# Pen-SLM — A Small Language Model for Automated Penetration Testing

Pen-SLM fine-tunes **Qwen3-14B** with a shared LoRA adapter using **GRPO** for two penetration-testing tasks:

* **Strategy generation** — predicts the next high-level strategy from the Penetration Testing Tree (PTT) and previous results.
* **Action planning** — converts a strategy into a concrete action plan, including MCP server selection and usage.

The two tasks are trained alternately using [`staged_training.py`](staged_training.py).

## Main Contributions

In this work, we propose a new reasoning dataset with a GRPO based fine-tuning technique to fine-tune an SLM for pentesting tasks. We provide the dataset, fine-tuning code, and the fine-tuned model in the following directories.
    - Dataset: ./Data/
    -fine-tuning code: staged_training.py
    -fine-tuned model: ./Trained_models/

## Requirements

To reproduce the training pipeline, the following resources are required.

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


## Run evaluation experiments

IF you are directly diving into experiments without fine-tuning the model, you need to pull the Pen-SLM model.
The trained `Pen-SLM` LoRA adapter is checked into this repo as a Git LFS
archive at `Trained_models/Pen-SLM-LoRA.zip`. Pull it before your first run:

Make sure you have the 48GB VRAM GPU (H100 recommended) to deploy the Pen-SLM and run the experiments.

```bash
git lfs pull
```

[Experiments/run_experiments.py](Experiments/run_experiments.py) extracts that
archive into `Trained_models/Pen-SLM` (if it isn't already extracted) and then
runs both scripts in [Experiments/Test-Set](Experiments/Test-Set):
[test_strategy_Pen-SLM.py](Experiments/Test-Set/test_strategy_Pen-SLM.py) and
[test_action_Pen-SLM.py](Experiments/Test-Set/test_action_Pen-SLM.py).

Run it from the repo root (unlike `staged_training.py`, this one expects to
be launched from the repo root, not a subdirectory):

```bash
python3 Experiments/run_experiments.py
```

- `--force-extract` re-extracts the model from the zip even if
  `Trained_models/Pen-SLM` already looks populated.
- `--only strategy` / `--only action` runs just one of the two eval scripts.

Requires `OPENAI_API_KEY` to be set (both eval scripts use `gpt-4o` as an
LLM judge, same as training).

Further experiments are explained in the Experiments directory.

