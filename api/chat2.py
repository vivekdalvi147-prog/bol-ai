from http.server import BaseHTTPRequestHandler
import json
import requests
import os
from datetime import datetime

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # 1. Input Data Read karna
            content_length = int(self.headers['Content-Length'])
            post_data = json.loads(self.rfile.read(content_length))

            user_msg = post_data.get('message')
            system_prompt = post_data.get('system')
            history = post_data.get('history', [])

            # 2. API Keys aur Firebase Config load karna
            all_keys = os.environ.get("MY_API_KEYS", "").split(",")
            FIREBASE_DB = "https://bol-ai-d94f4-default-rtdb.firebaseio.com"
            
            current_minute = datetime.now().strftime("%Y%m%d%H%M")
            selected_key = None
            selected_index = 0

            # 3. Key Rotation aur Rate Limiting Logic (Firebase Check)
            for i, key in enumerate(all_keys):
                usage_ref = f"{FIREBASE_DB}/api_usage/key_{i}/{current_minute}.json"
                try:
                    usage_res = requests.get(usage_ref).json()
                    count = usage_res if usage_res is not None else 0
                except:
                    count = 0
                
                if count < 5: # Limit check (5 requests per minute per key)
                    selected_key = key
                    selected_index = i + 1
                    # Usage count badhana
                    requests.put(usage_ref, data=json.dumps(count + 1))
                    break

            # Agar saari keys exhaust ho gayi hain
            if not selected_key:
                self.send_response(429)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Exhausted"}).encode())
                return

            # 4. Message History Prepare karna
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(history)
            messages.append({"role": "user", "content": user_msg})

            # 5. OpenRouter API Call (UPDATED MODEL HERE)
            ai_res = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {selected_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://your-site-url.com", # Apna site URL yahan dalein
                    "X-Title": "My AI App", # Apne App ka naam yahan dalein
                },
                data=json.dumps({
                    "model": "deepseek/deepseek-r1-0528:free", # Naya Model Updated
                    "messages": messages
                })
            )
            
            # Response handling
            if ai_res.status_code == 200:
                data = ai_res.json()
                data["api_index"] = selected_index # Bataega kaunsi key use hui

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())
            else:
                # Agar OpenRouter se error aaye
                self.send_response(ai_res.status_code)
                self.end_headers()
                self.wfile.write(ai_res.content)

        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
