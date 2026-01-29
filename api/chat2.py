from http.server import BaseHTTPRequestHandler
import json
import requests
import os
from datetime import datetime

# API usage tracking for rate limiting (per minute)
API_USAGE = {}

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # 1. Content Length check
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "No data received"}).encode())
                return

            # 2. Parse input data
            post_data = json.loads(self.rfile.read(content_length))
            user_msg = post_data.get('message')
            system_prompt = post_data.get('system', "You are a helpful assistant.")
            history = post_data.get('history', [])

            # 3. Get API Keys from environment variable (Updated Name)
            # Vercel me aap isi naam se key banayenge: my_ai_coder_bol-ai
            all_keys = os.environ.get("my_ai_coder_bol-ai", "").split(",")
            
            if not all_keys or all_keys == ['']:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "No API Keys found in environment variable 'my_ai_coder_bol-ai'"}).encode())
                return

            # 4. Key Rotation Logic (Same as before)
            current_minute = datetime.now().strftime("%Y-%m-%d %H:%M")
            selected_key = None
            selected_index = 0

            for i, key in enumerate(all_keys):
                key = key.strip() 
                if not key: continue

                if key not in API_USAGE:
                    API_USAGE[key] = {"time": current_minute, "count": 0}

                if API_USAGE[key]["time"] != current_minute:
                    API_USAGE[key]["time"] = current_minute
                    API_USAGE[key]["count"] = 0

                if API_USAGE[key]["count"] < 5: # Limit 5 requests per key per minute
                    selected_key = key
                    selected_index = i + 1
                    API_USAGE[key]["count"] += 1
                    break 

            if not selected_key:
                self.send_response(429) 
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "error": "Server Busy: All API keys reached their limit. Try again in 1 minute."
                }).encode())
                return

            # 5. Prepare Messages for OpenRouter
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(history)
            messages.append({"role": "user", "content": user_msg})

            # 6. OpenRouter API Call (Updated Model)
            ai_res = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {selected_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://bol-ai.vercel.app", 
                    "X-Title": "Bol AI",
                },
                data=json.dumps({
                    "model": "qwen/qwen3-coder:free", # Updated Model Name
                    "messages": messages
                })
            )
            
            # 7. Send Response back to frontend
            if ai_res.status_code == 200:
                data = ai_res.json()
                data["api_index"] = f"Key-{selected_index}" 

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())
            else:
                self.send_response(ai_res.status_code)
                self.end_headers()
                self.wfile.write(ai_res.content)

        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Internal Server Error: {str(e)}"}).encode())
