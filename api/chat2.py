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

            # Get API Keys from Vercel Environment
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

            # --- Key Selection Logic (30 RPM, 14000 RPD, 15000 TPM) ---
            for i, key in enumerate(all_keys):
                if key not in API_USAGE:
                    API_USAGE[key] = {"min": current_minute, "min_req": 0, "min_tokens": 0, "day": current_day, "day_req": 0}

                if API_USAGE[key]["min"] != current_minute:
                    API_USAGE[key]["min"] = current_minute
                    API_USAGE[key]["min_req"] = 0
                    API_USAGE[key]["min_tokens"] = 0
                
                if API_USAGE[key]["day"] != current_day:
                    API_USAGE[key]["day"] = current_day
                    API_USAGE[key]["day_req"] = 0

                if (API_USAGE[key]["min_req"] < 30 and 
                    API_USAGE[key]["day_req"] < 14000 and 
                    API_USAGE[key]["min_tokens"] < 15000):
                    selected_key = key
                    selected_index = i + 1
                    break

            if not selected_key:
                self.send_error_res(429, "All keys limit reached. Try after 1 minute.")
                return

            # --- Google GenAI Configuration ---
            genai.configure(api_key=selected_key)

            # Gemma 3 ke liye possible names jo Google accept karta hai
            # Pehla wala sabse zyada chances wala hai
            possible_model_names = ["gemma-3-27b", "models/gemma-3-27b", "gemma-3-27b-it"]
            
            response = None
            error_msg = ""

            # Chat history format convert karna
            chat_history = []
            for h in history:
                role = "user" if h['role'] == "user" else "model"
                chat_history.append({"role": role, "parts": [h['content']]})

            # Teeno model names try karega jab tak 200 OK na mil jaye
            for m_name in possible_model_names:
                try:
                    model = genai.GenerativeModel(model_name=m_name, system_instruction=system_prompt)
                    chat = model.start_chat(history=chat_history)
                    response = chat.send_message(user_msg)
                    if response:
                        actual_model_used = m_name
                        break
                except Exception as e:
                    error_msg = str(e)
                    continue # Agla name try karein agar 404 aaye

            if not response:
                self.send_error_res(404, f"Google Models (Gemma 3) Not Found. Last error: {error_msg}")
                return

            # --- Usage Tracking Update ---
            prompt_tokens = len(user_msg) // 3 # Approx
            res_tokens = len(response.text) // 3 # Approx
            total_tokens = prompt_tokens + res_tokens

            API_USAGE[selected_key]["min_req"] += 1
            API_USAGE[selected_key]["day_req"] += 1
            API_USAGE[selected_key]["min_tokens"] += total_tokens

            # --- Success Response ---
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "choices": [{"message": {"role": "assistant", "content": response.text}}],
                "api_index": f"Key-{selected_index}",
                "model_used": actual_model_used
            }).encode())

        except Exception as e:
            self.send_error_res(500, f"Critical Error: {str(e)}")

    def send_error_res(self, code, message):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())
