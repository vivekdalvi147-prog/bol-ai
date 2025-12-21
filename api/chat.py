from http.server import BaseHTTPRequestHandler
import json
import requests
import os

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = json.loads(self.rfile.read(content_length))
        user_message = post_data.get('message')

        # Vercel मधून सुरक्षित API Key वाचणे
        API_KEY = os.environ.get("MY_API_KEY")

        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            data=json.dumps({
                "model": "xiaomi/mimo-v2-flash:free",
                "messages": [{"role": "user", "content": user_message}]
            })
        )

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(response.text.encode())
