#!/usr/bin/env python3
"""
Ensure the Pen-SLM LoRA adapter is present under Trained_models/ (extracting it
from the Git-LFS-tracked Trained_models/Pen-SLM-LoRA.zip if needed), then run
the evaluation scripts in Experiments/Test-Set and/or the CTFKnow benchmark
against a locally-deployed Pen-SLM server.

Usage (from anywhere):
    python3 Experiments/run_experiments.py
    python3 Experiments/run_experiments.py --only strategy
    python3 Experiments/run_experiments.py --force-extract
    python3 Experiments/run_experiments.py --only ctfknow --ctfknow-questions <path>
"""
import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TRAINED_MODELS_DIR = REPO_ROOT / "Trained_models"
PEN_SLM_DIR = TRAINED_MODELS_DIR / "Pen-SLM"
PEN_SLM_ZIP = TRAINED_MODELS_DIR / "Pen-SLM-LoRA.zip"

TEST_SET_DIR = REPO_ROOT / "Experiments" / "Test-Set"
STRATEGY_SCRIPT = TEST_SET_DIR / "test_strategy_Pen-SLM.py"
ACTION_SCRIPT = TEST_SET_DIR / "test_action_Pen-SLM.py"

ADAPTER_MARKER_FILES = ("adapter_config.json",)

# ---- Local model server (Experiments/server.py) + CTFKnow benchmark ----
SERVER_DIR = REPO_ROOT / "Experiments"
SERVER_SCRIPT = SERVER_DIR / "server.py"
SERVER_PORT = 8083  # must match PORT in server.py
SERVER_HEALTH_URL = f"http://127.0.0.1:{SERVER_PORT}/health"

CTFKNOW_DIR = REPO_ROOT / "Experiments" / "CTFKnow"
CTFKNOW_RUN_SCRIPT = CTFKNOW_DIR / "run.py"
DEFAULT_CTFKNOW_QUESTIONS = CTFKNOW_DIR / "dataset" / "question_log_mix.json"
LOCAL_MODEL_NAME = "pen-slm"


def _looks_like_adapter_dir(path: Path) -> bool:
    return path.is_dir() and all((path / f).exists() for f in ADAPTER_MARKER_FILES)


def _is_lfs_pointer(path: Path) -> bool:
    """Git LFS files that haven't been pulled are small text pointers, not the
    real binary content -- detect that so we can give an actionable error."""
    try:
        with path.open("rb") as f:
            head = f.read(200)
    except OSError:
        return False
    return head.startswith(b"version https://git-lfs.github.com/spec/v1")


def ensure_model_available(force: bool = False) -> None:
    if PEN_SLM_DIR.exists() and not force:
        if _looks_like_adapter_dir(PEN_SLM_DIR):
            print(f"[run_experiments] Found existing model at {PEN_SLM_DIR}, skipping extraction.")
            return
        print(f"[run_experiments] {PEN_SLM_DIR} exists but doesn't look like a LoRA adapter "
              "(missing adapter_config.json) -- re-extracting into it.")

    if not PEN_SLM_ZIP.exists():
        raise SystemExit(
            f"[run_experiments] Neither {PEN_SLM_DIR} nor {PEN_SLM_ZIP} were found.\n"
            "  The model ships as a Git LFS archive checked into this repo -- pull it with:\n"
            "    git lfs pull\n"
            "  (or place the extracted adapter directly at Trained_models/Pen-SLM/)."
        )

    if _is_lfs_pointer(PEN_SLM_ZIP):
        raise SystemExit(
            f"[run_experiments] {PEN_SLM_ZIP} is a Git LFS pointer, not the actual archive "
            "(the LFS content hasn't been pulled yet). Run:\n"
            "    git lfs pull\n"
            "  then re-run this script."
        )

    print(f"[run_experiments] Extracting {PEN_SLM_ZIP} into {TRAINED_MODELS_DIR} ...")
    TRAINED_MODELS_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(PEN_SLM_ZIP) as zf:
        zf.extractall(TRAINED_MODELS_DIR)

    if not _looks_like_adapter_dir(PEN_SLM_DIR):
        raise SystemExit(
            f"[run_experiments] Extracted {PEN_SLM_ZIP} but {PEN_SLM_DIR} still doesn't contain "
            "an adapter_config.json -- check the archive's internal folder structure."
        )
    print("[run_experiments] Model ready.")


def _check_required_inputs(script_name: str, required_paths) -> bool:
    missing = [p for p in required_paths if not (REPO_ROOT / p).exists()]
    if missing:
        print(f"[run_experiments] Skipping {script_name}: missing input file(s): {', '.join(missing)}")
        print("[run_experiments]   These ship with the repo under Data/ -- check your checkout/clone "
              "(e.g. git lfs pull / git status) if they're missing.")
        return False
    return True


def run_script(script_path: Path, label: str) -> None:
    print(f"\n[run_experiments] ==== Running {label} ====")
    # test_strategy_Pen-SLM.py / test_action_Pen-SLM.py resolve their paths
    # (Data/test_data.csv, Trained_models/Pen-SLM, Results/) relative to their
    # own directory, so they must be launched with cwd=Test-Set/.
    subprocess.run([sys.executable, str(script_path)], cwd=TEST_SET_DIR, check=True)


def _server_is_ready() -> bool:
    try:
        with urllib.request.urlopen(SERVER_HEALTH_URL, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            return bool(data.get("model_loaded"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return False


def _wait_for_server(timeout_s: int, poll_interval: int = 10) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if _server_is_ready():
            return True
        time.sleep(poll_interval)
    return False


def start_local_server(quantized: bool = False) -> subprocess.Popen:
    print(f"[run_experiments] Launching local Pen-SLM server ({SERVER_SCRIPT}) on port {SERVER_PORT} "
          f"({'4-bit quantized' if quantized else 'full bf16'}) ...")
    cmd = [sys.executable, str(SERVER_SCRIPT)]
    if quantized:
        cmd.append("--quantized")
    # server.py resolves LORA_DIR as "./../Trained_models/Pen-SLM", so it must be
    # launched with cwd=Experiments/ (mirrors staged_training.py's ../Data convention).
    return subprocess.Popen(cmd, cwd=str(SERVER_DIR))


def stop_local_server(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    print("[run_experiments] Stopping local Pen-SLM server ...")
    proc.terminate()
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def run_ctfknow(questions_file: Path, server_timeout: int, quantized: bool = False) -> None:
    ensure_model_available()

    if not questions_file.exists():
        raise SystemExit(
            f"[run_experiments] CTFKnow question file not found: {questions_file}\n"
            "  This repo doesn't ship a ready-made graded question list -- generate one with\n"
            "  CTFKnow's own pipeline first (see Experiments/CTFKnow/README-new.md, steps K and Q):\n"
            "    cd Experiments/CTFKnow\n"
            "    python3 run.py K -i dataset/list.json -o dataset/knowledge.json\n"
            "    python3 run.py Q -i dataset/knowledge.json -o dataset/questions.json "
            "-q dataset/question_list.json\n"
            "  then pass the resulting file via --ctfknow-questions."
        )

    with questions_file.open("r", encoding="utf-8") as f:
        questions = json.load(f)
    if not isinstance(questions, list) or not questions or not {"question", "answer"} <= questions[0].keys():
        raise SystemExit(
            f"[run_experiments] {questions_file} doesn't look like a graded question-list file "
            "(expected a JSON list of objects with 'question' and 'answer' keys). For example, "
            "Experiments/CTFKnow/dataset/list_knwoledge_question.json is knowledge-extraction "
            "output, not a question list -- run CTFKnow's 'Q' step to produce one."
        )

    server_proc = None
    try:
        if _server_is_ready():
            print(f"[run_experiments] A model server is already healthy on port {SERVER_PORT}, reusing it.")
        else:
            server_proc = start_local_server(quantized=quantized)
            print(f"[run_experiments] Waiting up to {server_timeout}s for the model to load ...")
            if not _wait_for_server(server_timeout):
                raise SystemExit(
                    "[run_experiments] Server did not report healthy within the timeout. "
                    "Check GPU availability and that Trained_models/Pen-SLM loaded correctly, then retry "
                    "(pass --server-timeout to wait longer)."
                )
            print("[run_experiments] Server is up.")

        print("\n[run_experiments] ==== Running CTFKnow evaluation (single-choice) against pen-slm ====")
        subprocess.run(
            [sys.executable, "run.py", "E", "-M", "single", "-l", LOCAL_MODEL_NAME, "-o", str(questions_file)],
            cwd=str(CTFKNOW_DIR),
            check=True,
        )
    finally:
        if server_proc is not None:
            stop_local_server(server_proc)


def main():
    parser = argparse.ArgumentParser(
        description="Extract the Pen-SLM model (if needed) and run the Test-Set / CTFKnow experiments."
    )
    parser.add_argument("--force-extract", action="store_true",
                         help="Re-extract the model from Trained_models/Pen-SLM-LoRA.zip even if "
                              "Trained_models/Pen-SLM already exists.")
    parser.add_argument("--only", choices=["strategy", "action", "ctfknow", "all"], default="all",
                         help="Which experiment(s) to run. 'all' means strategy+action "
                              "(the Test-Set scripts); ctfknow is only run when explicitly selected, "
                              "since it deploys a local model server (default: all).")
    parser.add_argument("--ctfknow-questions", type=Path, default=DEFAULT_CTFKNOW_QUESTIONS,
                         help="Graded question-list JSON to evaluate CTFKnow against "
                              f"(default: {DEFAULT_CTFKNOW_QUESTIONS.relative_to(REPO_ROOT)}).")
    parser.add_argument("--server-timeout", type=int, default=1800,
                         help="Seconds to wait for the local Pen-SLM server to finish loading "
                              "the model before giving up (default: 1800).")
    parser.add_argument("--quantized-server", action="store_true",
                         help="Launch the local server (--only ctfknow) with 4-bit (nf4) "
                              "quantization instead of full bf16. Use this if you don't have "
                              "an A100-class GPU; see Experiments/README.md.")
    args = parser.parse_args()

    ensure_model_available(force=args.force_extract)

    # test_strategy_Pen-SLM.py / test_action_Pen-SLM.py write to ./../Results/
    # relative to their own directory, i.e. Experiments/Results/.
    (REPO_ROOT / "Experiments" / "Results").mkdir(parents=True, exist_ok=True)

    ran_any = False

    if args.only in ("strategy", "all"):
        if _check_required_inputs("test_strategy_Pen-SLM.py", ["Data/test_data.csv"]):
            run_script(STRATEGY_SCRIPT, "Strategy evaluation")
            ran_any = True

    if args.only in ("action", "all"):
        if _check_required_inputs("test_action_Pen-SLM.py", ["Data/test_data.csv"]):
            run_script(ACTION_SCRIPT, "Action evaluation")
            ran_any = True

    if args.only == "ctfknow":
        run_ctfknow(args.ctfknow_questions, args.server_timeout, quantized=args.quantized_server)
        ran_any = True

    if not ran_any:
        raise SystemExit(
            "[run_experiments] Nothing ran -- required test-data file(s) were missing (see notes above)."
        )


if __name__ == "__main__":
    main()
