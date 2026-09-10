"""OpenAI-compatible client + vision helpers + SVG/JSON extraction."""
import os
import re
import json
import base64
from openai import OpenAI

try:  # load .env if present (no-op if python-dotenv missing)
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def client_from_cfg(cfg):
    api = cfg.get("api", {})
    # env wins over config; supports .env
    base_url = os.environ.get("SVGBENCH_BASE_URL") or api.get("base_url")
    key = (os.environ.get("SVGBENCH_API_KEY")
           or os.environ.get(api.get("api_key_env", ""), ""))
    if not base_url:
        raise RuntimeError("no base_url: set SVGBENCH_BASE_URL in .env (or api.base_url)")
    if not key:
        raise RuntimeError("no api key: set SVGBENCH_API_KEY in .env")
    run = cfg.get("run", {})
    timeout = run.get("request_timeout", 1800)  # slow models (nvidia) need long timeouts
    retries = run.get("max_retries", 2)
    return OpenAI(base_url=base_url, api_key=key, timeout=timeout, max_retries=retries)


def _b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def img_part(path):
    return {"type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{_b64(path)}"}}


def text_part(t):
    return {"type": "text", "text": t}


def chat(client, model, system, user_content, max_tokens=12000, temperature=0.1):
    """Single-turn: system + one user message. user_content: str or content parts."""
    if isinstance(user_content, str):
        user_content = [text_part(user_content)]
    return chat_messages(client, model,
                         [{"role": "system", "content": system},
                          {"role": "user", "content": user_content}],
                         max_tokens, temperature)


def chat_messages(client, model, messages, max_tokens=12000, temperature=0.1):
    """Multi-turn: caller supplies the full messages list (session memory)."""
    resp = client.chat.completions.create(
        model=model, messages=messages,
        max_tokens=max_tokens, temperature=temperature,
    )
    return resp.choices[0].message.content or ""


def prune_old_images(messages):
    """Replace image parts in prior turns with a text stub to bound tokens.
    Keeps all text (SVG source + feedback trail); only the newest turn should
    carry live images. Mutates and returns messages."""
    for msg in messages:
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        new = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "image_url":
                new.append(text_part("[earlier image omitted]"))
            else:
                new.append(part)
        msg["content"] = new
    return messages


_SVG_FENCE = re.compile(r"```(?:svg|xml|html)?\s*(<svg[\s\S]*?</svg>)\s*```", re.I)
_SVG_BARE = re.compile(r"(<svg[\s\S]*?</svg>)", re.I)


def extract_svg(text):
    m = _SVG_FENCE.search(text) or _SVG_BARE.search(text)
    return m.group(1) if m else None


def extract_json(text):
    """Best-effort parse of the first JSON object in text."""
    m = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, re.I)
    blob = m.group(1) if m else None
    if blob is None:
        s = text.find("{")
        e = text.rfind("}")
        blob = text[s:e + 1] if s != -1 and e > s else None
    if not blob:
        return None
    try:
        return json.loads(blob)
    except Exception:
        return None
