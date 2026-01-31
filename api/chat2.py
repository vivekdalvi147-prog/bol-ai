from http.server import BaseHTTPRequestHandler
import json
import os
import google.generativeai as genai
from datetime import datetime

# Global usage tracking
API_USAGE = {}

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_error_res(400, "No data received")
                return

            post_data = json.loads(self.rfile.read(content_length))
            user_msg = post_data.get('message')
            system_prompt = post_data.get('system', "You are a helpful assistant.")
            history = post_data.get('history', [])

            # Load Keys from Vercel Env
            all_keys = os.environ.get("MY_CODER_BOL_AI", "").split(",")
            all_keys = [k.strip() for k in all_keys if k.strip()]

            if not all_keys:
                self.send_error_res(500, "API Keys missing in MY_CODER_BOL_AI")
                return

            now = datetime.now()
            current_minute = now.strftime("%Y-%m-%d %H:%M")
            current_day = now.strftime("%Y-%m-%d")

            selected_key = None
            selected_index = 0

            # --- Key Rotation & Limit Logic ---
            for i, key in enumerate(all_keys):
                if key not in API_USAGE:
                    API_USAGE[key] = {
                        "min": current_minute, "min_req": 0, "min_tokens": 0,
                        "day": current_day, "day_req": 0
                    }

                # Minute reset
                if API_USAGE[key]["min"] != current_minute:
                    API_USAGE[key]["min"] = current_minute
                    API_USAGE[key]["min_req"] = 0
                    API_USAGE[key]["min_tokens"] = 0
                
                # Day reset
                if API_USAGE[key]["day"] != current_day:
                    API_USAGE[key]["day"] = current_day
                    API_USAGE[key]["day_req"] = 0

                # Check all 3 limits: 30 RPM, 14000 RPD, 15000 TPM
                if (API_USAGE[key]["min_req"] < 30 and 
                    API_USAGE[key]["day_req"] < 14000 and 
                    API_USAGE[key]["min_tokens"] < 15000):
                    
                    selected_key = key
                    selected_index = i + 1
                    break

            if not selected_key:
                self.send_error_res(429, "All keys are at their limit. Try again in 1 minute.")
                return

            # --- Google AI Config ---
            genai.configure(api_key=selected_key)
            
            # Model Name: Aapke dashboard ke mutabik 'gemma-3-27b'
            model = genai.GenerativeModel(
                model_name="gemma-3-27b", 
                system_instruction=system_prompt
            )

            # Chat formatting
            chat_history = []
            for h in history:
                role = "user" if h['role'] == "user" else "model"
                chat_history.append({"role": role, "parts": [h['content']]})

            # Token calculation before sending (for TPM tracking)
            # Hum ek andaza lagate hain ya model.count_tokens use karte hain
            try:
                msg_tokens = model.count_tokens(user_msg).total_tokens
            except:
                msg_tokens = len(user_msg) // 4 # Fallback

            chat = model.start_chat(history=chat_history)
            response = chat.send_message(user_msg)

            # Update usage stats
            res_tokens = len(response.text) // 4
            total_tokens_used = msg_tokens + res_tokens
            
            API_USAGE[selected_key]["min_req"] += 1
            API_USAGE[selected_key]["day_req"] += 1
            API_USAGE[selected_key]["min_tokens"] += total_tokens_used

            # Send JSON response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            res_data = {
                "choices": [{"message": {"role": "assistant", "content": response.text}}],
                "api_index": f"Key-{selected_index}",
                "usage": {"total_tokens": total_tokens_used}
            }
            self.wfile.write(json.dumps(res_data).encode())

        except Exception as e:
            # Error return karega agar fir bhi 404 aaye
            self.send_error_res(500, str(e))

    def send_error_res(self, code, message):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())
