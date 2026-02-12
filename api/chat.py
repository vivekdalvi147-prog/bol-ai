from http.server import BaseHTTPRequestHandler
import json
import requests
import os
from datetime import datetime

# Global dictionary for Groq Key usage
API_USAGE = {}

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # --- १. युजर ओळख आणि सुरक्षा (Authentication) ---
            referer = self.headers.get('Referer', '')
            user_provided_key = self.headers.get('x-my-client-key', '')
            
            # Vercel मधून तुमच्या ग्राहकांच्या Keys ची लिस्ट मिळवा
            paid_clients = os.environ.get("PAID_CLIENTS", "").split(",")
            free_trial_key = "free-trial-api-123"

            is_allowed = False
            # वेबसाईटवरून फ्री ॲक्सेस
            if "bol-ai.vercel.app" in referer:
                is_allowed = True
            # पेड युजर किंवा ट्रायल युजर
            elif user_provided_key in paid_clients and user_provided_key != "":
                is_allowed = True
            elif user_provided_key == free_trial_key:
                is_allowed = True

            if not is_allowed:
                self.send_error_response(401, "Unauthorized: Please provide a valid API Key in 'x-my-client-key' header.")
                return

            # --- २. इनपुट डेटा वाचणे ---
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_error_response(400, "No data received")
                return

            post_data = json.loads(self.rfile.read(content_length))
            user_msg = post_data.get('message')
            system_prompt = post_data.get('system', "You are a helpful assistant.")
            history = post_data.get('history', [])

            # --- ३. Groq API Keys निवडणे (तुमचे मूळ लॉजिक) ---
            all_keys = os.environ.get("MY_API_KEYS", "").split(",")
            all_keys = [k.strip() for k in all_keys if k.strip()]
            
            if not all_keys:
                self.send_error_response(500, "No Groq API Keys found in environment")
                return

            now = datetime.now()
            current_minute = now.strftime("%Y-%m-%d %H:%M")
            current_day = now.strftime("%Y-%m-%d")

            selected_key = None
            selected_index = 0

            for i, key in enumerate(all_keys):
                if key not in API_USAGE:
                    API_USAGE[key] = {"day": current_day, "day_count": 0, "min": current_minute, "min_count": 0}
                stats = API_USAGE[key]
                if stats["min"] != current_minute:
                    stats["min"] = current_minute
                    stats["min_count"] = 0
                if stats["day"] != current_day:
                    stats["day"] = current_day
                    stats["day_count"] = 0

                if stats["min_count"] < 30 and stats["day_count"] < 1000:
                    selected_key = key
                    selected_index = i + 1
                    stats["min_count"] += 1
                    stats["day_count"] += 1
                    break

            if not selected_key:
                self.send_error_response(429, "Rate Limit Exceeded: All back-end keys are busy.")
                return

            # --- ४. Groq API कॉल करणे ---
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(history)
            messages.append({"role": "user", "content": user_msg})

            groq_url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {selected_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "moonshotai/kimi-k2-instruct",
                "messages": messages,
                "temperature": 0.7
            }

            ai_res = requests.post(groq_url, headers=headers, json=payload)
            
            if ai_res.status_code == 200:
                data = ai_res.json()
                data["api_usage_info"] = {
                    "key_index": selected_index,
                    "min_remaining": 30 - API_USAGE[selected_key]["min_count"],
                    "day_remaining": 1000 - API_USAGE[selected_key]["day_count"]
                }
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())
            else:
                self.send_response(ai_res.status_code)
                self.end_headers()
                self.wfile.write(ai_res.content)

        except Exception as e:
            self.send_error_response(500, f"Internal Server Error: {str(e)}")

    def send_error_response(self, code, message):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())
