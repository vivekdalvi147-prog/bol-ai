# ============================================
# Vivek Dalvi AI Server
# Made by Vivek ❤️
# Crafted with passion by Vivek Dalvi
# ============================================

from http.server import BaseHTTPRequestHandler
import json
import requests
import os


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        try:
            # Vivek Dalvi - Core Request Handler ❤️

            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_error_response(400, "No data received")
                return

            # Made by Vivek ❤️ - Parsing Client Data
            post_data = json.loads(self.rfile.read(content_length))
            user_msg = post_data.get('message', "")
            system_prompt = post_data.get('system', "You are a helpful assistant.")
            history = post_data.get('history', [])

            # Vivek Dalvi Secure Key Loader
            api_key = os.environ.get("ollama_my_api")

            if not api_key:
                self.send_error_response(500, "API Key 'ollama_my_api' not found in environment")
                return

            # Vivek AI Message Builder ❤️
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(history)

            if user_msg:
                messages.append({"role": "user", "content": user_msg})

            # Vivek Dalvi Cloud AI Connector
            ollama_url = "https://ollama.com/v1/chat/completions"

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": "kimi-k2.5:cloud",
                "messages": messages,
                "temperature": 0.7
            }

            # Made by Vivek ❤️ - Sending AI Request
            ai_res = requests.post(ollama_url, headers=headers, json=payload)

            # Vivek Dalvi Response Manager
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
            # Vivek Dalvi Error Handler ❤️
            self.send_error_response(500, f"Internal Server Error: {str(e)}")

    # Made by Vivek ❤️ - Custom Error Response
    def send_error_response(self, code, message):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())


# ============================================
# End of File
# Developed & Designed by Vivek Dalvi ❤️
# ============================================
