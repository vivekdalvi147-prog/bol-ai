from http.server import BaseHTTPRequestHandler
import json
import requests
import os
from datetime import datetime

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = json.loads(self.rfile.read(content_length))
        
        user_msg = post_data.get('message')
        system_prompt = post_data.get('system')
        history = post_data.get('history', [])

        # Vercel Settings मधील MY_API_KEYS (Comma separated)
        all_keys = os.environ.get("MY_API_KEYS", "").split(",")
        FIREBASE_DB = "https://bol-ai-d94f4-default-rtdb.firebaseio.com"
        
        current_minute = datetime.now().strftime("%Y%m%d%H%M")
        selected_key = None
        selected_index = 0

        # १९+ की मधून मोकळी की शोधणे (५ कॉल प्रति मिनिट मर्यादा)
        for i, key in enumerate(all_keys):
            usage_ref = f"{FIREBASE_DB}/api_usage/key_{i}/{current_minute}.json"
            usage_res = requests.get(usage_ref).json()
            count = usage_res if usage_res is not None else 0
            
            if count < 5:
                selected_key = key
                selected_index = i + 1  # Cloud 1, Cloud 2... साठी
                requests.put(usage_ref, data=json.dumps(count + 1))
                break

        if not selected_key:
            self.send_response(429)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Exhausted"}).encode())
            return

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_msg})

        try:
            ai_res = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {selected_key}",
                    "Content-Type": "application/json"
                },
                data=json.dumps({
                    "model": "xiaomi/mimo-v2-flash:free",
                    "messages": messages
                })
            )
            
            data = ai_res.json()
            data["api_index"] = selected_index # Front-end ला सांगण्यासाठी की कोणती Cloud API वापरली

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
            
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode())
