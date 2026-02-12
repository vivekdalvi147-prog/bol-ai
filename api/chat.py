from http.server import BaseHTTPRequestHandler
import json
import requests
import os
from datetime import datetime

API_USAGE = {}

class handler(BaseHTTPRequestHandler):
    # --- हे नवीन आहे: ब्राउझरच्या प्री-फ्लाईट रिक्वेस्टला उत्तर देण्यासाठी ---
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*') # सर्वांना परवानगी
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, x-my-client-key')
        self.end_headers()

    def do_POST(self):
        try:
            # --- १. CORS हेडर्स सेट करणे ---
            # (हेडर्स do_POST मध्ये सुद्धा लागतात)
            
            # २. युजर ओळख (Authentication)
            referer = self.headers.get('Referer', '')
            user_provided_key = self.headers.get('x-my-client-key', '')
            
            paid_clients = os.environ.get("PAID_CLIENTS", "").split(",")
            # ट्रिम करा (spaces काढण्यासाठी)
            paid_clients = [k.strip() for k in paid_clients]

            is_allowed = False
            if "bol-ai.vercel.app" in referer:
                is_allowed = True
            elif user_provided_key in paid_clients and user_provided_key != "":
                is_allowed = True
            elif user_provided_key == "free-trial-api-123":
                is_allowed = True

            if not is_allowed:
                self.send_error_response(401, "Unauthorized: Invalid Key")
                return

            # ३. इनपुट वाचणे
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = json.loads(self.rfile.read(content_length))
            user_msg = post_data.get('message')

            # ४. Groq API कॉल (तुमचा जुना कोड)
            all_keys = os.environ.get("MY_API_KEYS", "").split(",")
            all_keys = [k.strip() for k in all_keys if k.strip()]
            
            # (इथे तुमचे की रोटेशन लॉजिक चालू द्या...)
            # उदाहरणासाठी मी फक्त एक की वापरतोय:
            selected_key = all_keys[0] 

            groq_url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {selected_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "moonshotai/kimi-k2-instruct",
                "messages": [{"role": "user", "content": user_msg}]
            }

            ai_res = requests.post(groq_url, headers=headers, json=payload)
            
            # ५. रिस्पॉन्स पाठवताना CORS हेडर्स विसरू नका
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*') # खूप महत्त्वाचे
            self.end_headers()
            self.wfile.write(ai_res.content)

        except Exception as e:
            self.send_error_response(500, str(e))

    def send_error_response(self, code, message):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*') # इथे पण
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())
