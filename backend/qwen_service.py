
import os
import time
import ollama

OLLAMA_HOST = os.getenv(
    "OLLAMA_HOST",
    "http://localhost:11434"
)
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen3:4b")

# Keep the timeout configurable for slower computers.
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "120"))

client = ollama.Client(
    host=OLLAMA_HOST,
    timeout=OLLAMA_TIMEOUT,
)


def check_qwen_connection():
    """Check whether Ollama and the configured model are available."""
    try:
        result = client.list()
        model_names = [model.model for model in result.models]

        if QWEN_MODEL not in model_names:
            return {
                "status": "error",
                "message": f"Model {QWEN_MODEL} is not installed."
            }

        return {
            "status": "success",
            "model": QWEN_MODEL,
            "message": "Qwen3 is available."
        }

    except Exception as exc:
        return {
            "status": "error",
            "message": "Cannot connect to Ollama.",
            "detail": str(exc)
        }


def ask_qwen(prompt: str) -> str:
    """Generate a concise answer and log inference duration."""
    start_time = time.perf_counter()

    try:
        response = client.chat(
            model=QWEN_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a concise GIS assistant. "
                        "Follow the user's requested output format exactly. "
                        "For query planning, return only the requested JSON. "
                        "Do not include reasoning or unnecessary explanations."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            stream=False,
            think=False,
            options={
                "num_predict": 128,
                "temperature": 0.0,
            },
        )

        answer = (response.message.content or "").strip()

        # Some model responses may include reasoning markers.
        if "</think>" in answer:
            answer = answer.rsplit("</think>", 1)[-1].strip()

        elapsed = time.perf_counter() - start_time
        print(f"[QWEN] Inference completed in {elapsed:.2f}s")

        if not answer:
            raise RuntimeError(
                "Qwen3 returned an empty answer."
            )

        return answer

    except Exception as exc:
        elapsed = time.perf_counter() - start_time
        print(f"[QWEN] Failed after {elapsed:.2f}s: {exc}")
        raise
