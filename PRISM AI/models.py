"""OpenAI-compatible and local model services for PRISM AI."""

import json
import os
import re
import urllib.error
import urllib.request

import numpy as np


class ServiceError(RuntimeError):
    pass


# Ensure offline mode for cached HuggingFace models to avoid network delays
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

_MINILM_MODEL = None


def get_minilm():
    global _MINILM_MODEL
    if _MINILM_MODEL is None:
        try:
            from sentence_transformers import SentenceTransformer

            try:
                _MINILM_MODEL = SentenceTransformer(
                    "sentence-transformers/all-MiniLM-L6-v2",
                    local_files_only=True,
                )
            except Exception:
                _MINILM_MODEL = SentenceTransformer(
                    "sentence-transformers/all-MiniLM-L6-v2"
                )
        except Exception as exc:
            raise ServiceError(f"Failed to load all-MiniLM-L6-v2: {exc}") from exc
    return _MINILM_MODEL


def parse_json_response(raw_text):
    """Robustly parse JSON response from LLMs, handling markdown code fences, unescaped characters, and truncated output."""
    if not isinstance(raw_text, str):
        raise ValueError("Expected string input for JSON parsing.")
    text = raw_text.strip()
    # Strip thinking tags <think>...</think> if emitted by reasoning models
    text = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()
    # Strip markdown code blocks ```json ... ```
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    # Extract outermost JSON object if model added leading/trailing text
    if not (text.startswith("{") and text.endswith("}")):
        match = re.search(r"(\{[\s\S]*\})", text)
        if match:
            text = match.group(1)
    # Attempt 1: Standard JSON parsing with strict=False (allows newlines/control characters)
    try:
        return json.loads(text, strict=False)
    except Exception:
        pass
    # Attempt 2: Auto-repair unclosed quotes or missing closing braces from truncated tokens
    repaired = text
    quotes = len(re.findall(r'(?<!\\)"', repaired))
    if quotes % 2 != 0:
        repaired += '"'
    if not repaired.rstrip().endswith("}"):
        repaired += "}"
    try:
        return json.loads(repaired, strict=False)
    except Exception:
        pass
    # Attempt 3: Regex extraction for {"evidence": "..."} content
    ev_match = re.search(r'"evidence"\s*:\s*"((?:[^"\\]|\\.)*)', text)
    if ev_match:
        extracted = ev_match.group(1)
        extracted = extracted.replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t').replace('\\\\', '\\')
        return {"evidence": extracted}
    # Attempt 4: Fallback regex for unquoted or truncated values
    ev_fallback = re.search(r'"evidence"\s*:\s*([\s\S]+)', text)
    if ev_fallback:
        val = ev_fallback.group(1).strip().rstrip('"}').strip('"')
        return {"evidence": val}
    # Final attempt: let standard json.loads raise with clear error
    return json.loads(text)


def call(path, body):
    base = os.getenv("PRISM_API_BASE", "http://localhost:11434/v1").rstrip("/")
    headers = {"Content-Type": "application/json"}
    key = os.getenv("PRISM_API_KEY")
    if key:
        headers["Authorization"] = "Bearer " + key
    elif base.startswith("https://api.openai.com/"):
        raise ServiceError("Set PRISM_API_KEY in .env and restart the server.")
    req = urllib.request.Request(
        base + "/" + path, data=json.dumps(body).encode(), headers=headers
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as res:
            return json.load(res)
    except urllib.error.HTTPError as exc:
        raise ServiceError(
            f"Model service returned HTTP {exc.code}. Check model ID, credentials, and endpoint."
        ) from exc
    except (OSError, ValueError) as exc:
        raise ServiceError(
            f"Model service unavailable at {base}. Ensure Ollama or your LLM server is running."
        ) from exc


def chat(model, system, message):
    if not model:
        raise ServiceError("No chat model specified. Set PRISM_CHAT_MODEL in .env.")
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": message},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.0,
        "max_tokens": 4096,
        "options": {
            "num_predict": 4096,
            "temperature": 0.0,
        },
    }
    result = call("chat/completions", body)
    try:
        raw_content = result["choices"][0]["message"]["content"]
        return parse_json_response(raw_content)
    except (KeyError, TypeError, IndexError) as exc:
        raise ServiceError("Model response did not contain expected choices.") from exc
    except Exception as exc:
        raise ServiceError(f"Model response did not contain valid JSON: {exc}") from exc


def embed(texts):
    if isinstance(texts, str):
        texts = [texts]
    clean_texts = [str(t or "")[:8000] for t in texts]
    model = os.getenv("PRISM_EMBED_MODEL", "all-minilm")
    # Prefer local all-MiniLM-L6-v2 if requested or if no remote API key is set
    if "minilm" in model.lower() or not os.getenv("PRISM_API_KEY"):
        try:
            st = get_minilm()
            arr = st.encode(clean_texts, normalize_embeddings=True, show_progress_bar=False)
            return arr.astype(np.float32)
        except Exception:
            pass  # Fallback to API if local fails
    # Remote embeddings via OpenAI-compatible endpoint
    data = sorted(
        call("embeddings", {"model": model, "input": clean_texts})["data"],
        key=lambda x: x["index"],
    )
    if len(data) != len(clean_texts):
        raise ServiceError("Incomplete embedding response from remote service.")
    arr = np.asarray([item["embedding"] for item in data], dtype=np.float32)
    if arr.ndim != 2 or not np.isfinite(arr).all():
        raise ServiceError("Invalid embedding values returned.")
    return arr / np.maximum(np.linalg.norm(arr, axis=1, keepdims=True), 1e-12)
