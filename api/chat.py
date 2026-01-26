from http.server import BaseHTTPRequestHandler
import json
import requests
import os
from datetime import datetime

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # 1. Input parsing
        content_length = int(self.headers['Content-Length'])
        post_data = json.loads(self.rfile.read(content_length))
        
        user_msg = post_data.get('message')
        system_prompt = post_data.get('system')
        history = post_data.get('history', [])

        # 2. Key Rotation Logic (Firebase)
        all_keys = os.environ.get("MY_API_KEYS", "").split(",")
        FIREBASE_DB = "https://bol-ai-d94f4-default-rtdb.firebaseio.com"
        
        current_minute = datetime.now().strftime("%Y%m%d%H%M")
        selected_key = None
        selected_index = 0

        for i, key in enumerate(all_keys):
            usage_ref = f"{FIREBASE_DB}/api_usage/key_{i}/{current_minute}.json"
            usage_res = requests.get(usage_ref).json()
            count = usage_res if usage_res is not None else 0
            
            if count < 5:
                selected_key = key
                selected_index = i + 1
                requests.put(usage_ref, data=json.dumps(count + 1))
                break

        if not selected_key:
            self.send_response(429)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Exhausted"}).encode())
            return

        # 3. Message Construction
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_msg})

        try:
            # 4. API Call (Updated Headers & Model)
            ai_res = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {selected_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://bol-ai.vercel.app", # Aapka site URL
                    "X-Title": "Bol AI",                         # Site Title
                },
                data=json.dumps({
                    "model": "deepseek/deepseek-r1-0528:free", # DeepSeek R1 Model
                    "messages": messages
                })
            )
            data = ai_res.json()
            data["api_index"] = selected_index

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode())
