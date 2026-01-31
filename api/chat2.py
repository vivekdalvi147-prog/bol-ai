from http.server import BaseHTTPRequestHandler
import json
import os
import google.generativeai as genai # Stable Library
from datetime import datetime

# Usage tracking data
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

            # API Keys load karna
            all_keys = os.environ.get("MY_CODER_BOL_AI", "").split(",")
            all_keys = [k.strip() for k in all_keys if k.strip()]

            if not all_keys:
                self.send_error_res(500, "API Keys missing in environment")
                return

            now = datetime.now()
            current_minute = now.strftime("%Y-%m-%d %H:%M")
            current_day = now.strftime("%Y-%m-%d")

            selected_key = None
            selected_index = 0

            # Check Limits for each key
            for i, key in enumerate(all_keys):
                if key not in API_USAGE:
                    API_USAGE[key] = {
                        "min": current_minute, "min_req": 0, "min_tokens": 0,
                        "day": current_day, "day_req": 0
                    }

                # Reset logic
                if API_USAGE[key]["min"] != current_minute:
                    API_USAGE[key]["min"] = current_minute
                    API_USAGE[key]["min_req"] = 0
                    API_USAGE[key]["min_tokens"] = 0
                
                if API_USAGE[key]["day"] != current_day:
                    API_USAGE[key]["day"] = current_day
                    API_USAGE[key]["day_req"] = 0

                # Limits: 30 RPM, 14000 RPD, 15000 TPM
                if (API_USAGE[key]["min_req"] < 30 and 
                    API_USAGE[key]["day_req"] < 14000 and 
                    API_USAGE[key]["min_tokens"] < 15000):
                    
                    selected_key = key
                    selected_index = i + 1
                    break

            if not selected_key:
                self.send_error_res(429, "All keys exhausted for this minute/day.")
                return

            # Setup Google AI
            genai.configure(api_key=selected_key)
            
            # Gemma 3 27B handle karne ke liye model setup
            # Note: Agar 'gemma-3-27b' error de, to 'gemini-1.5-flash' try karein test ke liye
            model = genai.GenerativeModel(
                model_name="gemma-3-27b", 
                system_instruction=system_prompt
            )

            # History format change (Google format: user -> parts, model -> parts)
            chat_history = []
            for h in history:
                role = "user" if h['role'] == "user" else "model"
                chat_history.append({"role": role, "parts": [h['content']]})

            chat = model.start_chat(history=chat_history)
            
            # API Call
            response = chat.send_message(user_msg)

            # Token Calculation (Usage tracking)
            # Google response me usage_metadata deta hai
            prompt_tokens = model.count_tokens(user_msg).total_tokens
            res_tokens = model.count_tokens(response.text).total_tokens
            total_tokens = prompt_tokens + res_tokens

            # Update usage stats
            API_USAGE[selected_key]["min_req"] += 1
            API_USAGE[selected_key]["day_req"] += 1
            API_USAGE[selected_key]["min_tokens"] += total_tokens

            # Success response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            output = {
                "choices": [{"message": {"role": "assistant", "content": response.text}}],
                "usage": {"total_tokens": total_tokens},
                "api_index": f"Key-{selected_index}"
            }
            self.wfile.write(json.dumps(output).encode())

        except Exception as e:
            # Error hone par response dikhayega taki debug kar sakein
            self.send_error_res(500, f"Google API Error: {str(e)}")

    def send_error_res(self, code, message):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())
