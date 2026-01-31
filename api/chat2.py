from http.server import BaseHTTPRequestHandler
import json
import os
import google.generativeai as genai
from datetime import datetime

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

            # Get API Keys
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

                # Limits check
                if (API_USAGE[key]["min_req"] < 30 and API_USAGE[key]["day_req"] < 14000 and API_USAGE[key]["min_tokens"] < 15000):
                    selected_key = key
                    selected_index = i + 1
                    break

            if not selected_key:
                self.send_error_res(429, "All keys limit reached.")
                return

            # --- Sabse Important: Model Setup ---
            genai.configure(api_key=selected_key)
            
            # Yahan maine gemini-1.5-flash rakha hai kyunki Gemma 3 404 de raha hai
            # Agar Gemma hi chahiye toh 'gemma-2-27b-it' try karein
            model = genai.GenerativeModel(
                model_name="gemini-1.5-flash", 
                system_instruction=system_prompt
            )

            # Chat formatting
            chat_history = []
            for h in history:
                role = "user" if h['role'] == "user" else "model"
                chat_history.append({"role": role, "parts": [h['content']]})

            chat = model.start_chat(history=chat_history)
            response = chat.send_message(user_msg)

            # Usage Stats
            t_tokens = model.count_tokens(response.text).total_tokens + 100 
            API_USAGE[selected_key]["min_req"] += 1
            API_USAGE[selected_key]["day_req"] += 1
            API_USAGE[selected_key]["min_tokens"] += t_tokens

            # Success
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "choices": [{"message": {"role": "assistant", "content": response.text}}],
                "api_index": f"Key-{selected_index}"
            }).encode())

        except Exception as e:
            # Ye line aapko error dikhayegi ki 404 kyu aa raha hai
            self.send_error_res(500, str(e))

    def send_error_res(self, code, message):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())
