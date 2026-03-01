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
            user_msg = post_data.get('message', "")
            system_prompt = post_data.get('system', "You are a helpful assistant.")
            history = post_data.get('history',[])

            # 2. Get API Key from Environment
            # Aapne kaha tha 'ollama_my_api' name use karna hai
            api_key = os.environ.get("ollama_my_api")
            
            if not api_key:
                self.send_error_response(500, "API Key 'ollama_my_api' not found in environment")
                return

            # 3. Prepare Messages for Chat
            messages =[{"role": "system", "content": system_prompt}]
            messages.extend(history)
            if user_msg:
                messages.append({"role": "user", "content": user_msg})

            # 4. Call Ollama API (OpenAI Compatible Endpoint)
            # URL Ollama ke server ka hoga (jaise aapne pehle diya tha)
            ollama_url = "https://ollama.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "kimi-k2.5:cloud", # Yahan aap 'gpt-oss:120b' bhi daal sakte hain
                "messages": messages,
                "temperature": 0.7
            }

            # API Request
            ai_res = requests.post(ollama_url, headers=headers, json=payload)
            
            # 5. Send Response Back to Client
            if ai_res.status_code == 200:
                data = ai_res.json()

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())
            else:
                # Agar Ollama API se koi error aati hai
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
