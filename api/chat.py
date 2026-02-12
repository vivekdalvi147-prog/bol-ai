from http.server import BaseHTTPRequestHandler
import json
import requests
import os
from datetime import datetime

# Global dictionary for Groq Key usage
API_USAGE = {}

# --- Pastebin मधून System Instruction लोड करण्याचे फंक्शन ---
def get_system_instruction():
    # तुमची RAW Pastebin लिंक इथे टाका
    PASTEBIN_URL = "https://pastebin.com/raw/w0JNNj2W" 
    try:
        response = requests.get(PASTEBIN_URL, timeout=5)
        if response.status_code == 200:
            return response.text
        else:
            return "You are Bol AI, a helpful assistant." # Fallback जर एरर आला तर
    except:
        return "You are Bol AI, a helpful assistant." # Fallback जर इंटरनेट इश्यू आला तर

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        # CORS साठी हेडर्स
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, x-my-client-key')
        self.end_headers()

    def do_POST(self):
        try:
            # १. ओळख आणि सुरक्षा (Authentication)
            referer = self.headers.get('Referer', '')
            user_provided_key = self.headers.get('x-my-client-key', '')
            
            paid_clients = os.environ.get("PAID_CLIENTS", "").split(",")
            paid_clients = [k.strip() for k in paid_clients if k.strip()]
            
            is_allowed = False
            if "bol-ai.vercel.app" in referer:
                is_allowed = True
            elif user_provided_key in paid_clients and user_provided_key != "":
                is_allowed = True
            elif user_provided_key == "free-trial-api-123":
                is_allowed = True

            if not is_allowed:
                self.send_error_response(401, "Unauthorized: Please provide a valid Key.")
                return

            # २. इनपुट डेटा वाचणे
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = json.loads(self.rfile.read(content_length))
            user_msg = post_data.get('message')
            history = post_data.get('history', [])

            # ३. Pastebin मधून तुमची 'Full System Instruction' मिळवणे
            system_instruction = get_system_instruction()

            # ४. Groq API Keys निवडणे (तुमचे Rotation लॉजिक)
            all_keys = os.environ.get("MY_API_KEYS", "").split(",")
            all_keys = [k.strip() for k in all_keys if k.strip()]
            
            now = datetime.now()
            current_minute = now.strftime("%Y-%m-%d %H:%M")
            current_day = now.strftime("%Y-%m-%d")

            selected_key = None
            for key in all_keys:
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
                    stats["min_count"] += 1
                    stats["day_count"] += 1
                    break

            if not selected_key:
                self.send_error_response(429, "Rate Limit Exceeded: Server Busy.")
                return

            # ५. मेसेजेस तयार करणे (System Instruction सह)
            messages = [{"role": "system", "content": system_instruction}]
            messages.extend(history)
            messages.append({"role": "user", "content": user_msg})

            # ६. Groq ला कॉल करणे
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
            
            # ७. रिस्पॉन्स पाठवणे
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(ai_res.content)

        except Exception as e:
            self.send_error_response(500, f"Internal Error: {str(e)}")

    def send_error_response(self, code, message):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())
