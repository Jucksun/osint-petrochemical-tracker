"""Talk to a local Ollama server (free, runs on your own machine or Codespace).

One-time setup:   curl -fsSL https://ollama.com/install.sh | sh
Each session:     ollama serve &
Models (once):    ollama pull nomic-embed-text && ollama pull llama3.2:3b

Change models without editing code:  export CHAT_MODEL=qwen2.5:3b   (any model Ollama has pulled)
"""
import os

import requests

HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
if not HOST.startswith("http"):
    HOST = "http://" + HOST
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
CHAT_MODEL = os.getenv("CHAT_MODEL", "llama3.2:3b")


class LLMUnavailable(RuntimeError):
    """Ollama is not running, or a model has not been pulled."""


def _post(path: str, payload: dict, timeout: int) -> dict:
    try:
        r = requests.post(f"{HOST}{path}", json=payload, timeout=timeout)
    except requests.RequestException as e:
        raise LLMUnavailable("Ollama is not reachable. Start it with: ollama serve &") from e
    if r.status_code != 200:
        raise LLMUnavailable(f"Ollama returned {r.status_code}: {r.text[:200]}. If the model is "
                             f"missing, run: ollama pull {payload.get('model')}")
    return r.json()


def embed(texts: list[str], model: str | None = None) -> list[list[float]]:
    """One vector per text. Ollama returns unit-length vectors."""
    return _post("/api/embed", {"model": model or EMBED_MODEL, "input": texts}, 300)["embeddings"]


def chat(messages: list[dict], model: str | None = None) -> str:
    payload = {"model": model or CHAT_MODEL, "messages": messages, "stream": False,
               "options": {"temperature": 0, "num_ctx": 4096}}
    return _post("/api/chat", payload, 600)["message"]["content"].strip()
