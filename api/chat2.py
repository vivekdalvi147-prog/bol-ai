from http.server import BaseHTTPRequestHandler
import json
import os
import google.generativeai as genai
from datetime import datetime

# Global usage tracking (Note: Vercel par ye reset hota rehta hai, jo limit ke liye achha hai)
API_USAGE = {}

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_error_res(400, "No data received")
                return

            post_data = json.loads(self.rfile.read(content_length))
            user_msg = post_data.get('message', '')
            system_prompt = post_data.get('system', "You are a helpful assistant.")
            history = post_data.get('history', [])

            # 1. API Keys Load Karna
            all_keys = os.environ.get("MY_CODER_BOL_AI", "").split(",")
            all_keys = [k.strip() for k in all_keys if k.strip()]

            if not all_keys:
                self.send_error_res(500, "No API Keys found in Environment Variable")
                return

            now = datetime.now()
            current_minute = now.strftime("%Y-%m-%d %H:%M")
            current_day = now.strftime("%Y-%m-%d")

            selected_key = None
            selected_index = 0

            # 2. Key Selection Logic (30 RPM, 14000 RPD, 15000 TPM)
            for i, key in enumerate(all_keys):
                if key not in API_USAGE:
                    API_USAGE[key] = {"min": current_minute, "min_req": 0, "min_tokens": 0, "day": current_day, "day_req": 0}

                # Resets
                if API_USAGE[key]["min"] != current_minute:
                    API_USAGE[key]["min"] = current_minute
                    API_USAGE[key]["min_req"] = 0
                    API_USAGE[key]["min_tokens"] = 0
                if API_USAGE[key]["day"] != current_day:
                    API_USAGE[key]["day"] = current_day
                    API_USAGE[key]["day_req"] = 0

                # Check Constraints
                if (API_USAGE[key]["min_req"] < 30 and 
                    API_USAGE[key]["day_req"] < 14000 and 
                    API_USAGE[key]["min_tokens"] < 15000):
                    selected_key = key
                    selected_index = i + 1
                    break

            if not selected_key:
                self.send_error_res(429, "Server Busy: All keys reached limits. Try in 1 minute.")
                return

            # 3. Google AI Setup
            genai.configure(api_key=selected_key)
            
            # --- MODEL SELECTION FIX ---
            # Hum pehle 'gemma-3-27b' try karenge, agar wo nahi mila toh Flash par switch karenge
            try:
                model = genai.GenerativeModel(
                    model_name="models/gemma-3-27b", # Correct Format
                    system_instruction=system_prompt
                )
            except:
                # Fallback agar Gemma 3 recognize nahi ho raha
                model = genai.GenerativeModel(model_name="gemini-1.5-flash")

            # 4. History Formatting
            chat_history = []
            for h in history:
                # Google only accepts 'user' and 'model'
                role = "user" if h['role'].lower() == "user" else "model"
                chat_history.append({"role": role, "parts": [h['content']]})

            # 5. Call API
            chat = model.start_chat(history=chat_history)
            response = chat.send_message(user_msg)

            # 6. Tracking Tokens
            # Google response.usage_metadata se sahi tokens milte hain
            try:
                t_tokens = response.usage_metadata.total_token_count
            except:
                t_tokens = (len(user_msg) + len(response.text)) // 3 # Fallback estimation

            API_USAGE[selected_key]["min_req"] += 1
            API_USAGE[selected_key]["day_req"] += 1
            API_USAGE[selected_key]["min_tokens"] += t_tokens

            # 7. Final Response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            final_json = {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": response.text
                    }
                }],
                "api_index": f"Key-{selected_index}",
                "usage": {"total_tokens": t_tokens}
            }
            self.wfile.write(json.dumps(final_json).encode())

        except Exception as e:
            # Agar error aaye toh response mein dikhega ki exact error kya hai
            self.send_error_res(500, f"AI Error: {str(e)}")

    def send_error_res(self, code, message):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())
