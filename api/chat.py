from http.server import BaseHTTPRequestHandler
import json
import requests
import os

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = json.loads(self.rfile.read(content_length))
        
        user_message = post_data.get('message')
        system_prompt = post_data.get('system_prompt', "You are bol.ai")

        # ही API KEY आपण नंतर Vercel मध्ये सेव्ह करू, कोडमध्ये नाही!
        API_KEY = os.environ.get("OPENROUTER_API_KEY")

        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            data=json.dumps({
                "model": "xiaomi/mimo-v2-flash:free",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ]
            })
        )

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(response.text.encode())
