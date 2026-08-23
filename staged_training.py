import argparse
from typing import List

import torch
from peft import LoraConfig, get_peft_model, TaskType, PeftModel

from transformers import AutoModelForCausalLM, AutoTokenizer

from train_strategy_qwen14b import train_strategy, _ensure_strategy_dataset, dataset as strategy_dataset
from train_action_qwen3_14B import train_action, _ensure_action_dataset, dataset as action_dataset

TOTAL_STEPS = 4000
SWITCH_INTERVALS = [800, 400, 100, 50, 10]
#SWITCH_INTERVALS = [400, 100, 50, 10]
FINAL_OUTPUT_DIR = "./../Trained_models/staged_final"
lora_adapter_path = "./../Trained_models/staged_final/checkpoint-strategy_800"


def build_shared_lora_model(lora_adapter_path, model_name: str = "Qwen/Qwen3-14B", lora_rank: int = 8):
    """Create one shared base Qwen3-14B and attach a single LoRA adapter used by all episodes."""
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "left"

    base_model = AutoModelForCausalLM.from_pretrained(
        model_name,
        device_map="auto",
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
    )
    base_model.config.use_cache = False

    lora_config = LoraConfig(
        r=lora_rank,
        lora_alpha=lora_rank * 2,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0.0,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )

    if lora_adapter_path == None:
        model = get_peft_model(base_model, lora_config)
    else:
        model = PeftModel.from_pretrained(
            base_model,
            lora_adapter_path,
            is_trainable=True,   # True if you want to continue training
        )
    
    model.enable_input_require_grads()
    model.gradient_checkpointing_enable()
    if not hasattr(model, "warnings_issued"):
        model.warnings_issued = {}
    model.print_trainable_parameters()
    return tokenizer, model


def _make_cyclic_indices(start_idx: int, length: int, dataset_size: int) -> List[int]:
    """Return a cyclic row list that wraps around the dataset boundary when needed."""
    if dataset_size <= 0:
        raise ValueError("The dataset is empty; staged training cannot proceed.")
    if length <= 0:
        return []

    indices: List[int] = []
    cursor = start_idx % dataset_size
    for _ in range(length):
        indices.append(cursor)
        cursor = (cursor + 1) % dataset_size
    return indices


def build_switch_schedule(total_steps: int = TOTAL_STEPS) -> List[int]:
    """Build the paired stage sizes used by the alternating training schedule."""
    schedule: List[int] = []
    remaining = total_steps
    idx = 0

    while remaining > 0:
        interval = SWITCH_INTERVALS[idx % len(SWITCH_INTERVALS)]
        if interval > remaining:
            interval = remaining
        schedule.append(interval)
        remaining -= interval
        idx += 1

    return schedule


def run_staged_training(
    strategy_dataset_part=None,
    action_dataset_part=None,
    total_steps: int = TOTAL_STEPS,
    output_dir_strategy: str = FINAL_OUTPUT_DIR,
    output_dir_action: str = FINAL_OUTPUT_DIR,
    start_task: str = "strategy",
):
    """Alternate between strategy and action phases using the same row window for both tasks.

    The training is still LoRA-only: each stage wraps the base Qwen model with PEFT adapters,
    leaving the base model frozen while the adapter weights are updated.
    """
    schedule = build_switch_schedule(total_steps)

    tokenizer, current_model = build_shared_lora_model(lora_adapter_path)

    use_cyclic_window = (strategy_dataset_part is None and action_dataset_part is None)
    strategy_dataset_ready = _ensure_strategy_dataset(tokenizer)
    action_dataset_ready = _ensure_action_dataset(tokenizer)
    dataset_size = min(len(strategy_dataset_ready), len(action_dataset_ready))

    steps_run = 0
    row_cursor = 0

    for interval in schedule:
        if use_cyclic_window:
            window_indices = _make_cyclic_indices(row_cursor, interval, dataset_size)
            strategy_part = window_indices
            action_part = window_indices
            print(
                f"Paired episode: strategy and action both use rows {window_indices[:min(len(window_indices), 8)]}... "
                f"for {interval} optimization steps"
            )
        else:
            strategy_part = strategy_dataset_part
            action_part = action_dataset_part

        print(f"Running paired stage for {interval} optimization steps (completed: {steps_run}/{total_steps})")

        if start_task == 'strategy':
            train_strategy(
                current_model=current_model,
                dataset_part=strategy_part,
                output_dir=output_dir_strategy,
                max_steps=interval,
                tokenizer_obj=tokenizer,
            )
    
            train_action(
                current_model=current_model,
                dataset_part=action_part,
                output_dir=output_dir_action,
                max_steps=interval,
                tokenizer_obj=tokenizer,
            )

        else:
            train_action(
                current_model=current_model,
                dataset_part=action_part,
                output_dir=output_dir_action,
                max_steps=interval,
                tokenizer_obj=tokenizer,
            )
            train_strategy(
                current_model=current_model,
                dataset_part=strategy_part,
                output_dir=output_dir_strategy,
                max_steps=interval,
                tokenizer_obj=tokenizer,
            )
        

        steps_run += interval * 2
        row_cursor = (row_cursor + interval) % dataset_size
        print(f"Finished paired stage: {steps_run}/{total_steps} steps completed")

    print(f"Staged training finished after {steps_run} optimization steps.")
    return current_model


def _parse_args():
    parser = argparse.ArgumentParser(description="Two-stage episodic GRPO training for strategy and action tasks.")
    parser.add_argument("--strategy-part", type=str, default=None,
                        help="Dataset slice for strategy training, e.g. 'slice(0,1000)' or a row count.")
    parser.add_argument("--action-part", type=str, default=None,
                        help="Dataset slice for action training, e.g. 'slice(0,1000)' or a row count.")
    parser.add_argument("--total-steps", type=int, default=TOTAL_STEPS,
                        help="Total optimization steps for the staged run.")
    parser.add_argument("--start-task", choices=["strategy", "action"], default="strategy",
                        help="Which task starts the episodic cycle.")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    def _resolve_part(raw_value):
        if raw_value is None or raw_value == "None":
            return None
        if raw_value.isdigit():
            return int(raw_value)
        if raw_value.startswith("slice("):
            try:
                namespace = {}
                exec("value = " + raw_value, {}, namespace)
                return namespace["value"]
            except Exception as exc:
                raise ValueError(f"Invalid slice spec: {raw_value!r}") from exc
        return raw_value

    strategy_part = _resolve_part(args.strategy_part)
    action_part = _resolve_part(args.action_part)

    run_staged_training(
        strategy_dataset_part=strategy_part,
        action_dataset_part=action_part,
        total_steps=args.total_steps,
        start_task=args.start_task,
    )
