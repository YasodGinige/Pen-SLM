"""
Model Server for Hugging Face + PEFT LoRA models (no Unsloth)
Serves inference through FastAPI REST endpoints

Full bf16 inference of the Qwen3-14B base model (+ LoRA) needs roughly 30-35GB
of VRAM, so a single 40GB+ A100-class GPU is the baseline target. If you don't
have one, pass --quantized (or set PEN_SLM_4BIT=1) to load the base model in
4-bit (nf4, via bitsandbytes) instead, which fits in ~10-12GB and runs on
consumer-grade GPUs at some cost to quality/throughput.
"""
import argparse
import os
import time
import uuid
from typing import Dict, List, Optional

import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from peft import PeftModel
from pydantic import BaseModel, Field
from transformers import AutoModelForCausalLM, AutoTokenizer
from transformers import BitsAndBytesConfig

# ============================================================================
# CONFIGURATION
# ============================================================================

# Model configuration
MODEL_NAME = "Qwen/Qwen3-14B"  # Base model
LORA_DIR = "./../Trained_models/Pen-SLM"  # Path to your LoRA checkpoint
MAX_SEQ_LENGTH = 32000
LORA_RANK = 8
SEED = 2187

# Set from --quantized / PEN_SLM_4BIT before load_model() runs (see __main__).
USE_4BIT = os.environ.get("PEN_SLM_4BIT", "0").lower() in ("1", "true", "yes")

# Server configuration
HOST = "0.0.0.0"
PORT = 8083

# Device configuration
DEVICE = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

# ============================================================================
# GLOBAL VARIABLES
# ============================================================================

app = FastAPI(
    title="HF + PEFT Model Server",
    description="API server for querying Hugging Face models with LoRA adapters",
    version="1.0.0",
)

model = None
tokenizer = None

# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================


class GenerateRequest(BaseModel):
    """Request model for text generation"""

    prompt: str = Field(..., description="Input prompt for generation")
    max_new_tokens: int = Field(default=2500, description="Maximum tokens to generate")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    top_p: float = Field(default=0.9, ge=0.0, le=1.0, description="Nucleus sampling probability")
    top_k: int = Field(default=50, ge=0, description="Top-k sampling parameter")
    repetition_penalty: float = Field(default=1.1, ge=1.0, description="Repetition penalty")
    do_sample: bool = Field(default=True, description="Whether to use sampling")

    class Config:
        json_schema_extra = {
            "example": {
                "prompt": "What is penetration testing?",
                "max_new_tokens": 1200,
                "temperature": 0.3,
                "top_p": 0.7,
            }
        }


class GenerateResponse(BaseModel):
    """Response model for text generation"""

    prompt: str
    generated_text: str
    full_text: str
    tokens_generated: int


class HealthResponse(BaseModel):
    """Health check response"""

    status: str
    model_loaded: bool
    cuda_available: bool
    cuda_device_count: int
    cuda_devices: List[str]


# ---- OpenAI-compatible chat endpoint (so external tools that speak the
#      OpenAI SDK, e.g. CTFKnow's run.py, can target this server via `base_url`) ----


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    """Subset of the OpenAI chat-completions request schema. Streaming is not supported."""

    model: str = "pen-slm"
    messages: List[ChatMessage]
    max_tokens: int = Field(default=1024, description="Maximum tokens to generate")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    top_k: int = Field(default=50, ge=0)
    stream: bool = False
    enable_thinking: bool = Field(
        default=False,
        description="Qwen3 chat-template flag; off by default so callers expecting a short, "
        "direct answer (e.g. a single multiple-choice letter) don't get a <think> preamble.",
    )


class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]


# ============================================================================
# MODEL LOADING
# ============================================================================


def load_model() -> None:
    """Load Hugging Face model and attach a PEFT LoRA adapter."""
    global model, tokenizer

    if model is not None and tokenizer is not None:
        return

    print("[server] Loading model & tokenizer...")
    print(f"[server] MODEL_NAME={MODEL_NAME}")
    print(f"[server] LORA_DIR={LORA_DIR}")
    print(f"[server] USE_4BIT={USE_4BIT}")
    print(f"[server] CUDA_VISIBLE_DEVICES={os.environ.get('CUDA_VISIBLE_DEVICES', '')}")
    print("[server] torch.version.cuda =", torch.version.cuda)
    print("[server] torch.cuda.is_available() =", torch.cuda.is_available())
    print("[server] torch.cuda.device_count() =", torch.cuda.device_count())

    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA is not available. You likely masked the GPU with CUDA_VISIBLE_DEVICES "
            "or your job/container wasn't started with GPU access."
        )

    torch.manual_seed(SEED)

    # Tokenizer
    _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
    if _tokenizer.pad_token is None:
        _tokenizer.pad_token = _tokenizer.eos_token
    _tokenizer.padding_side = "left"

    # Full bf16 needs ~30-35GB VRAM (A100-class); --quantized trades quality/speed
    # for a ~10-12GB footprint that runs on smaller GPUs.
    if USE_4BIT:
        print("[server] Loading base model in 4-bit (nf4) via bitsandbytes...")
        quant_kwargs = {
            "quantization_config": BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_use_double_quant=True,
            )
        }
    else:
        quant_kwargs = {"torch_dtype": torch.bfloat16}

    # Force single-GPU placement: the only visible GPU is cuda:0

    _model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        device_map='auto',
        trust_remote_code=True,
        **quant_kwargs,
    )

    # For inference, cache should be ON (huge speedup)
    _model.config.use_cache = True

    # Load LoRA adapter
    if os.path.exists(LORA_DIR):
        print(f"[server] Loading LoRA weights from {LORA_DIR}")
        _model = PeftModel.from_pretrained(_model, LORA_DIR)
    else:
        print(f"[server] Warning: LoRA directory {LORA_DIR} not found, using base model only")

    _model.eval()

    print("[server] model param device =", next(_model.parameters()).device)

    model, tokenizer = _model, _tokenizer
    print("[server] Model loaded successfully!")
    print(f"[server] torch.cuda.is_available()={torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"[server] torch.cuda.device_count()={torch.cuda.device_count()}")
        for i in range(torch.cuda.device_count()):
            print(f"[server] GPU {i}: {torch.cuda.get_device_name(i)}")


# ============================================================================
# API ENDPOINTS
# ============================================================================


@app.on_event("startup")
async def startup_event():
    """Load model on server startup"""
    print("[server] Starting up...")
    load_model()
    print("[server] Ready to serve requests!")


class RootResponse(BaseModel):
    message: str
    version: str
    endpoints: Dict[str, str]

@app.get("/", response_model=RootResponse)
async def root():
    return {
        "message": "HF + PEFT Model Server",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "generate": "/generate (POST)",
            "batch_generate": "/batch_generate (POST)",
            "chat_completions": "/v1/chat/completions (POST, OpenAI-compatible)",
            "docs": "/docs",
        },
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    cuda_devices = []
    if torch.cuda.is_available():
        cuda_devices = [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]

    return HealthResponse(
        status="healthy" if model is not None else "model_not_loaded",
        model_loaded=model is not None,
        cuda_available=torch.cuda.is_available(),
        cuda_device_count=torch.cuda.device_count() if torch.cuda.is_available() else 0,
        cuda_devices=cuda_devices,
    )


@app.post("/generate", response_model=GenerateResponse)
async def generate_text(request: GenerateRequest):
    """Generate text from the model."""
    if model is None or tokenizer is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        inputs = tokenizer(
            request.prompt,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=MAX_SEQ_LENGTH,
        )

        if torch.cuda.is_available():
            inputs = {k: v.to(DEVICE) for k, v in inputs.items()}

        input_length = int(inputs["attention_mask"][0].sum().item())

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=request.max_new_tokens,
                temperature=request.temperature,
                top_p=request.top_p,
                top_k=request.top_k,
                repetition_penalty=request.repetition_penalty,
                do_sample=request.do_sample,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )

        full_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
        generated_ids = outputs[0][input_length:]
        generated_text = tokenizer.decode(generated_ids, skip_special_tokens=True).strip()

        return GenerateResponse(
            prompt=request.prompt,
            generated_text=generated_text,
            full_text=full_text,
            tokens_generated=int(generated_ids.shape[0]),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed specific: {str(e)}")


@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest):
    """OpenAI-compatible chat endpoint. Point the OpenAI SDK's `base_url` at
    http://<host>:<port>/v1 to use this server as a drop-in local backend."""
    if model is None or tokenizer is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    if request.stream:
        raise HTTPException(status_code=400, detail="stream=True is not supported by this server")

    try:
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        try:
            text = tokenizer.apply_chat_template(
                messages,
                add_generation_prompt=True,
                tokenize=False,
                enable_thinking=request.enable_thinking,
            )
        except TypeError:
            # Chat template doesn't accept enable_thinking (non-Qwen3 tokenizer).
            text = tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)

        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=MAX_SEQ_LENGTH)
        if torch.cuda.is_available():
            inputs = {k: v.to(DEVICE) for k, v in inputs.items()}

        input_length = inputs["input_ids"].shape[1]

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=request.max_tokens,
                temperature=request.temperature,
                top_p=request.top_p,
                top_k=request.top_k,
                do_sample=request.temperature > 0,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )

        generated_text = tokenizer.decode(
            outputs[0][input_length:], skip_special_tokens=True
        ).strip()

        return ChatCompletionResponse(
            id=f"chatcmpl-{uuid.uuid4().hex}",
            created=int(time.time()),
            model=request.model,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=generated_text),
                    finish_reason="stop",
                )
            ],
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@app.post("/batch_generate")
async def batch_generate(
    prompts: List[str],
    max_new_tokens: int = 1200,
    temperature: float = 0.3,
    top_p: float = 0.9,
):
    """Generate text for multiple prompts in batch."""
    if model is None or tokenizer is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    if len(prompts) == 0:
        raise HTTPException(status_code=400, detail="Empty prompts list")

    try:
        inputs = tokenizer(
            prompts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=MAX_SEQ_LENGTH,
        )

        if torch.cuda.is_available():
            inputs = {k: v.to(DEVICE) for k, v in inputs.items()}

        input_lengths = inputs["attention_mask"].sum(dim=1).tolist()

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                do_sample=True,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )

        results = []
        for i, output in enumerate(outputs):
            full_text = tokenizer.decode(output, skip_special_tokens=True)
            generated_ids = output[int(input_lengths[i]):]
            generated_text = tokenizer.decode(generated_ids, skip_special_tokens=True).strip()
            results.append(
                {
                    "prompt": prompts[i],
                    "generated_text": generated_text,
                    "full_text": full_text,
                    "tokens_generated": int(generated_ids.shape[0]),
                }
            )

        return {"results": results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch generation failed: {str(e)}")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser(description="Pen-SLM (Qwen3-14B + LoRA) inference server")
    arg_parser.add_argument(
        "--quantized", "--4bit", dest="quantized", action="store_true",
        help="Load the base model in 4-bit (nf4) via bitsandbytes instead of full bf16. "
             "Use this if you don't have an A100-class GPU (~30-35GB VRAM); 4-bit needs "
             "roughly 10-12GB. Equivalent to setting PEN_SLM_4BIT=1.",
    )
    arg_parser.add_argument("--host", default=HOST, help=f"Bind host (default: {HOST})")
    arg_parser.add_argument("--port", type=int, default=PORT, help=f"Bind port (default: {PORT})")
    cli_args = arg_parser.parse_args()

    USE_4BIT = USE_4BIT or cli_args.quantized
    HOST = cli_args.host
    PORT = cli_args.port

    print(f"[server] Starting server on {HOST}:{PORT}")
    print(f"[server] API docs will be available at http://{HOST}:{PORT}/docs")
    print(f"[server] 4-bit quantized inference: {'ENABLED' if USE_4BIT else 'disabled (full bf16)'}")

    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
