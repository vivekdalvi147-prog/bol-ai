import os
import requests
import json

CEREBRAS_API_KEY = os.environ.get("CEREBRAS_API_KEY_vivek")
CEREBRAS_API_URL = "https://api.cerebras.ai/v1/chat/completions"

def cerebras_chat(message, system="", history=None):
    if history is None:
        history = []

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    if history:
        messages.extend(history)
    if message:
        messages.append({"role": "user", "content": message})

    headers = {
        "Authorization": f"Bearer {CEREBRAS_API_KEY_vivek}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "qwen-3-235b-a22b-instruct-2507",
        "messages": messages,
        "max_completion_tokens": 1500,
        "temperature": 0.2,
        "top_p": 0.8,
        "stream": False
    }

    response = requests.post(CEREBRAS_API_URL, headers=headers, json=payload)
    if response.status_code == 200:
        data = response.json()
        return data["choices"][0]["message"]["content"]
    else:
        return f"Error {response.status_code}: {response.text}"

if __name__ == "__main__":
    user_message = "Hello, how are you?"
    system_prompt = "You are a helpful assistant"
    result = cerebras_chat(user_message, system_prompt)
    print("AI Response:", result)
