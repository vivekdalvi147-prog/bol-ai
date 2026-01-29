from http.server import BaseHTTPRequestHandler
import json
import requests
import os
from datetime import datetime

API_USAGE = {}

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "No data received"}).encode())
                return

            post_data = json.loads(self.rfile.read(content_length))
            
            user_msg = post_data.get('message')
            system_prompt = post_data.get('system')
            history = post_data.get('history', [])

            all_keys = os.environ.get("MY_API_KEYS", "").split(",")
            
            if not all_keys or all_keys == ['']:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "No API Keys found in environment"}).encode())
                return

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

                if API_USAGE[key]["count"] < 5:
                    selected_key = key
                    selected_index = i + 1
                    
                    API_USAGE[key]["count"] += 1
                    break 

            if not selected_key:
                self.send_response(429) 
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "error": "Server Busy: All API keys are currently at limit. Please try again in 1 minute."
                }).encode())
                return

            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(history)
            messages.append({"role": "user", "content": user_msg})

            ai_res = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {selected_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://bol-ai.vercel.app", 
                    "X-Title": "Bol AI",
                },
                data=json.dumps({
                    "model": "tngtech/deepseek-r1t2-chimera:free", 
                    "messages": messages
                })
            )
            
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
