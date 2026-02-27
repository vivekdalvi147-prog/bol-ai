from http.server import BaseHTTPRequestHandler
import json
import requests
import os

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # 1. Parse Input Data
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_error_response(400, "No data received")
                return

            post_data = json.loads(self.rfile.read(content_length))
            user_msg = post_data.get('message')
            system_prompt = post_data.get('system', "You are a helpful assistant.")
            history = post_data.get('history', [])

            if not user_msg:
                self.send_error_response(400, "Message is required")
                return

            # 2. Get OpenAI API Key from Vercel Environment
            openai_key = os.environ.get("open_ai")

            if not openai_key:
                self.send_error_response(500, "OpenAI API key not found in environment")
                return

            # 3. Prepare Messages
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(history)
            messages.append({"role": "user", "content": user_msg})

            # 4. OpenAI API Call
            openai_url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {openai_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "gpt-4o-mini",  # Fast and cheaper model
                "messages": messages,
                "temperature": 0.7
            }

            ai_res = requests.post(openai_url, headers=headers, json=payload)

            # 5. Send Response
            self.send_response(ai_res.status_code)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(ai_res.content)

        except Exception as e:
            self.send_error_response(500, f"Internal Server Error: {str(e)}")

    def send_error_response(self, code, message):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())
