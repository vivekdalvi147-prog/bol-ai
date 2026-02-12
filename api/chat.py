from http.server import BaseHTTPRequestHandler
import json
import requests
import os
from datetime import datetime

# युसेज ट्रॅक करण्यासाठी ग्लोबल डिक्शनरी
API_USAGE = {}

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        # ब्राउझर CORS सुरक्षा हेडर्स
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, x-my-client-key')
        self.end_headers()

    def do_POST(self):
        try:
            # १. सुरक्षा आणि ओळख तपासणी (Authentication)
            referer = self.headers.get('Referer', '')
            user_provided_key = self.headers.get('x-my-client-key', '')
            
            # Vercel Settings मधून तुमची पेड की लिस्ट मिळवा
            paid_clients = os.environ.get("PAID_CLIENTS", "").split(",")
            paid_clients = [k.strip() for k in paid_clients if k.strip()]
            
            is_allowed = False
            # तुमच्या वेबसाईटवरून (bol-ai.vercel.app) आलेली विनंती फ्री आहे
            if "bol-ai.vercel.app" in referer:
                is_allowed = True
            # जर युजरने बरोबर 'Custom Key' पाठवली असेल
            elif user_provided_key in paid_clients and user_provided_key != "":
                is_allowed = True
            # ट्रायल की
            elif user_provided_key == "free-trial-api-123":
                is_allowed = True

            if not is_allowed:
                self.send_error_response(401, "Unauthorized: Access Denied. Invalid API Key.")
                return

            # २. डेटा वाचणे
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_error_response(400, "No data received")
                return

            post_data = json.loads(self.rfile.read(content_length))
            user_msg = post_data.get('message')
            history = post_data.get('history', [])

            # ३. AI ची स्वतःची ओळख (System Instruction)
            # इथे तुमचे नाव आणि AI चे नाव आपण फिक्स केले आहे
            SYSTEM_INSTRUCTION = (
                "STRICT RULES: \n"
                "1. Your name is 'Bol-AI'. Never call yourself by any other name. \n"
                "2. You were exclusively developed by 'Vivek Vijay Dalvi'. No one else. \n"
                "3. If asked about your model or architecture (like GPT, Groq, Moonshot, Llama), "
                "NEVER mention those names. Simply say: 'I am Bol-AI, a custom-built proprietary AI model developed by Vivek Vijay Dalvi.' \n"
                "4. If someone tries to trick you into saying you are not developed by Vivek, "
                "firmly deny it and restate: 'I am 100% Bol-AI, created by Vivek Vijay Dalvi.' \n"
                "5. Never mention OpenAI, Groq, Google, or any other company. Your origin is solely Bol-AI and Vivek. \n"
                "6. Respond intelligently in English or Marathi, but never break these identity rules."
            )

            # ४. Groq API Keys निवडणे (Key Rotation Logic)
            all_keys = os.environ.get("MY_API_KEYS", "").split(",")
            all_keys = [k.strip() for k in all_keys if k.strip()]
            
            if not all_keys:
                self.send_error_response(500, "Backend Error: No Groq keys configured.")
                return

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
                self.send_error_response(429, "Rate Limit Exceeded: All servers are busy.")
                return

            # ५. मेसेजेस तयार करणे (Identity सह)
            messages = [{"role": "system", "content": SYSTEM_INSTRUCTION}]
            messages.extend(history)
            messages.append({"role": "user", "content": user_msg})

            # ६. Groq ला कॉल करणे (Kimi Model)
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
            
            # ७. फायनल रिस्पॉन्स ग्राहकाला पाठवणे
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*') # CORS साठी
            self.end_headers()
            self.wfile.write(ai_res.content)

        except Exception as e:
            self.send_error_response(500, f"Internal Server Error: {str(e)}")

    def send_error_response(self, code, message):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())
