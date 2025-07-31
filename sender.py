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
        payload["grammar"] = grammar  # inject grammar if present

    log_payload(payload)


    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[Error from llama-server: {e}]"

def log_payload(payload, log_path="llama_payload.log"):
    timestamp = datetime.utcnow().isoformat()
    with open(log_path, "a") as f:
        f.write(f"[{timestamp}]\n{json.dumps(payload, indent=2)}\n\n")