
from http.server import BaseHTTPRequestHandler
import json
import requests
import os

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = json.loads(self.rfile.read(content_length))
        
        user_msg = post_data.get('message')
        system_prompt = post_data.get('system_prompt')
        history = post_data.get('history', [])

        # Vercel Settings मध्ये ही की 'MY_API_KEY' या नावाने सेव्ह कर
        api_key = os.environ.get("MY_API_KEY")

        full_messages = [{"role": "system", "content": system_prompt}]
        full_messages.extend(history)
        full_messages.append({"role": "user", "content": user_msg})

        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            data=json.dumps({
                "model": "xiaomi/mimo-v2-flash:free",
                "messages": full_messages
            })
        )

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(response.text.encode())
