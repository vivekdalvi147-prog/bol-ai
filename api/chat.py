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

            # 2. API Keys aur Firebase Setup
            all_keys = os.environ.get("MY_API_KEYS", "").split(",")
            if not all_keys or all_keys == ['']:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "No API Keys found in environment variables"}).encode())
                return

            FIREBASE_DB = "https://bol-ai-d94f4-default-rtdb.firebaseio.com"
            current_minute = datetime.now().strftime("%Y%m%d%H%M")
            selected_key = None
            selected_index = 0

            # 3. Key Rotation Logic (Check Usage)
            for i, key in enumerate(all_keys):
                usage_ref = f"{FIREBASE_DB}/api_usage/key_{i}/{current_minute}.json"
                try:
                    usage_res = requests.get(usage_ref).json()
                except:
                    usage_res = 0
                
                count = usage_res if usage_res is not None else 0
                
                # Limit set to 5 requests per minute per key
                if count < 5:
                    selected_key = key
                    selected_index = i + 1
                    # Usage count update karna
                    requests.put(usage_ref, data=json.dumps(count + 1))
                    break

            # Agar saari keys exhaust ho gayi hain
            if not selected_key:
                self.send_response(429)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "All keys exhausted. Try again later."}).encode())
                return

            # 4. Messages Structure banana
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(history)
            messages.append({"role": "user", "content": user_msg})

            # 5. OpenRouter API Call (New Model with Reasoning)
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {selected_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://bol-ai.vercel.app", # Optional: Identify your app
                "X-Title": "Bol AI" # Optional
            }
            
            payload = {
                "model": "openai/gpt-oss-120b:free", # Updated Model
                "messages": messages,
                "reasoning": {"enabled": True} # Enabled Reasoning
            }

            ai_res = requests.post(url, headers=headers, data=json.dumps(payload))
            
            # Check if upstream API failed
            if ai_res.status_code != 200:
                self.send_response(ai_res.status_code)
                self.end_headers()
                self.wfile.write(ai_res.content)
                return

            # 6. Success Response Send karna
            data = ai_res.json()
            data["api_index"] = selected_index

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())

        except Exception as e:
            # Global Error Handling
            self.send_response(500)
            self.end_headers()
            error_msg = {"error": str(e)}
            self.wfile.write(json.dumps(error_msg).encode())
