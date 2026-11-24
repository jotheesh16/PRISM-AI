"""OpenAI-compatible and local model services for PRISM AI."""

import json
import os
import re
from urllib.parse import urlsplit
import urllib.error
import urllib.request

import numpy as np


class ServiceError(RuntimeError):
    pass


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
    """Robustly parse JSON response from LLMs, handling markdown code fences and control characters while rejecting truncated output."""
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
        else:
            raise ServiceError(f"Model returned partial or non-JSON output: {text[:100]}")
    # Attempt 1: Standard JSON parsing with strict=False (allows newlines/control characters)
    try:
        return json.loads(text, strict=False)
    except Exception:
        pass
    # Attempt 2: Regex extraction for complete closed {"evidence": "..."} content
    ev_match = re.search(r'^\s*\{\s*"evidence"\s*:\s*"([\s\S]*)"\s*\}\s*$', text)
    if ev_match:
        extracted = ev_match.group(1).replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t').replace('\\\\', '\\')
        return {"evidence": extracted}
    # Final attempt: let standard json.loads raise with clear error
    return json.loads(text)


def call(path, body, timeout=None, native=False):
    base = os.getenv("PRISM_API_BASE", "http://127.0.0.1:11434/v1").rstrip("/")
    # On Windows, localhost can resolve to IPv6 ::1 where Ollama does not listen, causing WinError 10060
    base = base.replace("://localhost:", "://127.0.0.1:").replace("://localhost/", "://127.0.0.1/")
    if base.endswith("://localhost"):
        base = base[:-9] + "127.0.0.1"
    if native:
        base = base.removesuffix("/v1")
    headers = {"Content-Type": "application/json"}
    key = os.getenv("PRISM_API_KEY")
    if key:
        headers["Authorization"] = "Bearer " + key
    elif base.startswith("https://api.openai.com/"):
        raise ServiceError("Set PRISM_API_KEY in .env and restart the server.")
    req = urllib.request.Request(
        base + "/" + path, data=json.dumps(body).encode(), headers=headers
    )
    request_timeout = timeout or int(os.getenv("PRISM_TIMEOUT", "180"))
    try:
        with urllib.request.urlopen(req, timeout=request_timeout) as res:
            return json.load(res)
    except urllib.error.HTTPError as exc:
        raise ServiceError(
            f"Model service returned HTTP {exc.code}. Check model ID, credentials, and endpoint."
        ) from exc
    except (OSError, ValueError) as exc:
        raise ServiceError(
            f"Model service unavailable at {base}. Ensure Ollama or your LLM server is running."
        ) from exc


def chat(model, system, message, schema=None):
    if not model:
        raise ServiceError("No chat model specified. Set PRISM_CHAT_MODEL in .env.")
    system_prompt = system.strip()
    if "json" not in system_prompt.lower():
        system_prompt += "\nAlways return your response formatted as a valid JSON object."
    system_prompt += "\nReturn only the complete JSON object, without commentary."
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
        "temperature": 0.0,
        "max_tokens": 2048,
        "response_format": {"type": "json_object"},
    }
    endpoint = urlsplit(os.getenv("PRISM_API_BASE", "http://127.0.0.1:11434/v1"))
    native = endpoint.port == 11434 and isinstance(message, str)
    if native:
        body = {"model": model, "messages": body["messages"], "stream": False,
                "think": False, "format": schema or "json",
                "options": {"temperature": 0, "num_predict": 2048}}
    result = call("api/chat" if native else "chat/completions", body, timeout=120, native=native)
    try:
        msg = result["message"] if native else result["choices"][0]["message"]
        raw_content = msg.get("content") or ""
        parsed = parse_json_response(raw_content)
        if not isinstance(parsed, dict):
            raise ValueError("Expected a JSON object")
        return parsed
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
    if "minilm" in model.lower():
        st = get_minilm()
        arr = st.encode(clean_texts, normalize_embeddings=True, show_progress_bar=False)
        return arr.astype(np.float32)
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
