# Utility functions for talking to a locally hosted LLaMA server

import requests
import json
from datetime import datetime
from pathlib import Path
import time

def send_chat_completion(
    system_prompt,
    user_prompt,
    model="llama-chat",
    temperature=0.7,
    max_tokens=300,
    url="http://10.0.0.101:8080/v1/chat/completions",
    grammar=None,
):
    # Send a chat completion request and return the assistant's reply
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    if grammar:
        payload["grammar"] = grammar  # ✅ inject grammar if present

    log_payload(payload)


    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[Error from llama-server: {e}]"

def log_payload(payload):
    # Append the outgoing payload to ``llama_payload.log`` for debugging
    # Step 1: Pre-process content fields to unescape \n
    for msg in payload.get("messages", []):
        if isinstance(msg.get("content"), str):
            # Convert "\\n" into real newlines
            msg["content"] = msg["content"].encode("utf-8").decode("unicode_escape")

    # Step 2: Dump with real formatting
    log_path = Path("llama_payload.log")
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"# {timestamp}\n")
        f.write(json.dumps(payload, indent=2, ensure_ascii=False))
        f.write("\n---\n")