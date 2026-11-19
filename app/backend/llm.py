"""
LLM provider layer for the chatbot.

Tries an OpenAI-compatible API first, then Google Gemini, and returns None (or yields nothing)
when neither is configured or both fail, so callers can fall back to the
rule-based answers in main.py.

"OpenAI-compatible" includes free/local options by setting OPENAI_BASE_URL:
  - Ollama (local, free):   OPENAI_BASE_URL=http://localhost:11434/v1  OPENAI_MODEL=llama3.1
  - Groq (free tier):       OPENAI_BASE_URL=https://api.groq.com/openai/v1  OPENAI_MODEL=llama-3.3-70b-versatile
  - OpenRouter, LM Studio and others work the same way.

Messages use the OpenAI shape: [{"role": "user" | "assistant", "content": str}].
"""
import os
from typing import Iterator, List, Optional

import env_config  # noqa: F401  (loads the project .env before keys are read)

OPENAI_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
# Someone pasted an OpenAI key into the Gemini slot before; keep tolerating it.
if GEMINI_KEY and GEMINI_KEY.startswith("sk-") and not OPENAI_KEY:
    OPENAI_KEY, GEMINI_KEY = GEMINI_KEY, None

OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL") or None
# Local servers like Ollama don't need a real key, but the client requires one.
if OPENAI_BASE_URL and not OPENAI_KEY:
    OPENAI_KEY = "not-needed"

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
# Tried in order: if Google is overloaded (503) or retires a model (404), the next one answers.
GEMINI_MODELS = [m.strip() for m in os.getenv("GEMINI_MODEL", "gemini-3.5-flash,gemini-3.1-flash-lite").split(",") if m.strip()]
MAX_OUTPUT_TOKENS = int(os.getenv("CHAT_MAX_OUTPUT_TOKENS", "900"))
TEMPERATURE = 0.6
REQUEST_TIMEOUT = 45

_openai_client = None
_gemini_client = None


def is_configured() -> bool:
    return bool(OPENAI_KEY or GEMINI_KEY)


def _openai():
    global _openai_client
    if _openai_client is None and OPENAI_KEY:
        import openai
        _openai_client = openai.OpenAI(api_key=OPENAI_KEY, base_url=OPENAI_BASE_URL, timeout=REQUEST_TIMEOUT, max_retries=1)
    return _openai_client


def _gemini():
    global _gemini_client
    if _gemini_client is None and GEMINI_KEY:
        from google import genai
        _gemini_client = genai.Client(api_key=GEMINI_KEY)
    return _gemini_client


def _gemini_request(system: str, messages: List[dict]):
    from google.genai import types
    contents = [
        types.Content(role="model" if m["role"] == "assistant" else "user", parts=[types.Part(text=m["content"])])
        for m in messages if m.get("content")
    ]
    config = types.GenerateContentConfig(
        system_instruction=system,
        temperature=TEMPERATURE,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        # Flash "thinks" by default and that budget comes out of max_output_tokens.
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )
    return contents, config


def _openai_messages(system: str, messages: List[dict]) -> List[dict]:
    return [{"role": "system", "content": system}] + [
        {"role": m["role"], "content": m["content"]} for m in messages if m.get("content")
    ]


def generate(system: str, messages: List[dict]) -> Optional[str]:
    """One-shot completion. Returns None when no provider produced text."""
    client = _openai()
    if client:
        try:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=_openai_messages(system, messages),
                max_tokens=MAX_OUTPUT_TOKENS,
                temperature=TEMPERATURE,
            )
            text = response.choices[0].message.content if response.choices else None
            if text and text.strip():
                return text.strip()
        except Exception as e:
            print(f"[llm] OpenAI call failed: {e}")

    client = _gemini()
    if client:
        contents, config = _gemini_request(system, messages)
        for model in GEMINI_MODELS:
            try:
                response = client.models.generate_content(model=model, contents=contents, config=config)
                if response.text and response.text.strip():
                    return response.text.strip()
            except Exception as e:
                print(f"[llm] Gemini call failed ({model}): {e}")

    return None


def stream(system: str, messages: List[dict]) -> Iterator[str]:
    """
    Streams text chunks. If a provider fails before sending anything, the next
    provider is tried. If it fails midway, the stream simply ends (the caller
    keeps what already arrived).
    """
    client = _openai()
    if client:
        sent_any = False
        try:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=_openai_messages(system, messages),
                max_tokens=MAX_OUTPUT_TOKENS,
                temperature=TEMPERATURE,
                stream=True,
            )
            for chunk in response:
                if not chunk.choices:
                    continue
                piece = chunk.choices[0].delta.content
                if piece:
                    sent_any = True
                    yield piece
            if sent_any:
                return
        except Exception as e:
            print(f"[llm] OpenAI stream failed: {e}")
            if sent_any:
                return

    client = _gemini()
    if client:
        contents, config = _gemini_request(system, messages)
        for model in GEMINI_MODELS:
            sent_any = False
            try:
                for chunk in client.models.generate_content_stream(model=model, contents=contents, config=config):
                    if chunk.text:
                        sent_any = True
                        yield chunk.text
                if sent_any:
                    return
            except Exception as e:
                print(f"[llm] Gemini stream failed ({model}): {e}")
                if sent_any:
                    return
