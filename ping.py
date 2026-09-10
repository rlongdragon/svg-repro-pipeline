#!/usr/bin/env python3
"""Ping every model in models.txt to check availability + latency."""
import os, time
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv(dotenv_path=".env")

cli = OpenAI(base_url=os.environ["SVGBENCH_BASE_URL"],
             api_key=os.environ["SVGBENCH_API_KEY"], timeout=150, max_retries=0)

for m in [l.strip() for l in open("models.txt") if l.strip() and not l.startswith("#")]:
    t = time.time()
    try:
        r = cli.chat.completions.create(
            model=m, messages=[{"role": "user", "content": "say pong"}], max_tokens=8)
        reply = (r.choices[0].message.content or "").strip()[:20]
        print("OK   %-42s %6.1fs  %r" % (m, time.time() - t, reply), flush=True)
    except Exception as e:
        print("FAIL %-42s %6.1fs  %s: %s" % (m, time.time() - t, type(e).__name__, str(e)[:80]), flush=True)
