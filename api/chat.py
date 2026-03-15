from http.server import BaseHTTPRequestHandler
import json
import requests
import os
from datetime import datetime

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_error_response(400, "No data")
                return

            post_data = json.loads(self.rfile.read(content_length))
            user_msg = post_data.get('message', '')
            system_prompt = post_data.get('system', "")
            history = post_data.get('history', [])

            api_key = os.environ.get("Vivek_huggingface_best", "")
            if not api_key:
                self.send_error_response(500, "API key missing")
                return

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            if history:
                messages.extend(history)

            if user_msg:
                messages.append({"role": "user", "content": user_msg})

            url = "https://router.huggingface.co/v1/chat/completions"

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": "zai-org/GLM-5:novita",
                "messages": messages
            }

            ai_res = requests.post(url, headers=headers, json=payload)

            if ai_res.status_code == 200:
                data = ai_res.json()
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())
            else:
                self.send_response(ai_res.status_code)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(ai_res.content)

        except Exception as e:
            self.send_error_response(500, str(e))

    def send_error_response(self, code, message):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())
