from http.server import BaseHTTPRequestHandler
import json
import os
import requests
from datetime import datetime

# Global usage tracking
API_USAGE = {}

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = json.loads(self.rfile.read(content_length))
            
            user_msg = post_data.get('message', '')
            system_prompt = post_data.get('system', 'You are a helpful assistant.')
            history = post_data.get('history', [])

            # 1. API Keys Load
            all_keys = os.environ.get("MY_CODER_BOL_AI", "").split(",")
            all_keys = [k.strip() for k in all_keys if k.strip()]

            if not all_keys:
                self.send_error_res(500, "API Keys missing in Vercel Env")
                return

            now = datetime.now()
            current_min = now.strftime("%Y-%m-%d %H:%M")
            current_day = now.strftime("%Y-%m-%d")

            selected_key = None
            selected_index = 0

            # 2. Key Selection Logic (30 RPM, 14000 RPD, 15000 TPM)
            for i, key in enumerate(all_keys):
                if key not in API_USAGE:
                    API_USAGE[key] = {"min": current_min, "min_req": 0, "min_tokens": 0, "day": current_day, "day_req": 0}

                # Reset Minute/Day
                if API_USAGE[key]["min"] != current_min:
                    API_USAGE[key]["min"] = current_min
                    API_USAGE[key]["min_req"] = 0
                    API_USAGE[key]["min_tokens"] = 0
                if API_USAGE[key]["day"] != current_day:
                    API_USAGE[key]["day"] = current_day
                    API_USAGE[key]["day_req"] = 0

                # Check Limits
                if (API_USAGE[key]["min_req"] < 30 and 
                    API_USAGE[key]["day_req"] < 14000 and 
                    API_USAGE[key]["min_tokens"] < 15000):
                    selected_key = key
                    selected_index = i + 1
                    break

            if not selected_key:
                self.send_error_res(429, "All keys limit reached. Try after 1 minute.")
                return

            # 3. Prepare Payload (Google Official Format)
            # Gemma 3 27B ka official ID aksar 'gemma-3-27b' hota hai
            model_id = "gemma-3-27b" 
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={selected_key}"
            
            # Format History
            contents = []
            for h in history:
                role = "user" if h['role'] == "user" else "model"
                contents.append({"role": role, "parts": [{"text": h['content']}]})
            
            # Add Current Message
            contents.append({"role": "user", "parts": [{"text": user_msg}]})

            payload = {
                "contents": contents,
                "system_instruction": {"parts": [{"text": system_prompt}]},
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 2048
                }
            }

            # 4. Official API Call
            response = requests.post(url, headers={'Content-Type': 'application/json'}, json=payload)
            res_json = response.json()

            if response.status_code != 200:
                # Agar Gemma 404 de, toh Gemini Flash try karein (Auto-Fallback)
                model_id = "gemini-1.5-flash"
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={selected_key}"
                response = requests.post(url, headers={'Content-Type': 'application/json'}, json=payload)
                res_json = response.json()

            # 5. Extract Text and Usage
            try:
                ai_text = res_json['candidates'][0]['content']['parts'][0]['text']
                total_tokens = res_json.get('usageMetadata', {}).get('totalTokenCount', 500)
            except Exception:
                self.send_error_res(response.status_code, f"API Error: {json.dumps(res_json)}")
                return

            # Update Stats
            API_USAGE[selected_key]["min_req"] += 1
            API_USAGE[selected_key]["day_req"] += 1
            API_USAGE[selected_key]["min_tokens"] += total_tokens

            # 6. Response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "choices": [{"message": {"role": "assistant", "content": ai_text}}],
                "api_index": f"Key-{selected_index}",
                "model": model_id
            }).encode())

        except Exception as e:
            self.send_error_res(500, str(e))

    def send_error_res(self, code, message):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())
