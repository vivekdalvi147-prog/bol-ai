from http.server import BaseHTTPRequestHandler
import json
import requests
import os
from datetime import datetime

# Global storage for usage tracking
# Note: Vercel serverless functions me memory reset hoti rehti hai, 
# but temporary rotation ke liye yeh kaam karega.
API_USAGE = {}

class handler(BaseHTTPRequestHandler):
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def do_POST(self):
        try:
            # 1. Parse Input
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_error_response(400, "No data received")
                return

            post_data = json.loads(self.rfile.read(content_length))
            user_msg = post_data.get('message')
            system_prompt = post_data.get('system', "You are a helpful assistant.")
            history = post_data.get('history', [])

            if not user_msg and not history:
                self.send_error_response(400, "Message content is required")
                return

            # 2. Get API Keys from Environment Variable
            all_keys_str = os.environ.get("MY_CODER_BOL_AI", "")
            all_keys = [k.strip() for k in all_keys_str.split(",") if k.strip()]
            
            if not all_keys:
                self.send_error_response(500, "No API Keys found in Environment Variables")
                return

            # 3. Key Selection with Rate Limiting (40/min and 40/day)
            now = datetime.now()
            current_minute = now.strftime("%Y-%m-%d %H:%M")
            current_day = now.strftime("%Y-%m-%d")
            
            selected_key = None
            selected_index = 0

            for i, key in enumerate(all_keys):
                if key not in API_USAGE:
                    API_USAGE[key] = {
                        "last_min": current_minute, "min_count": 0,
                        "last_day": current_day, "day_count": 0
                    }

                # Reset Minute count if minute changed
                if API_USAGE[key]["last_min"] != current_minute:
                    API_USAGE[key]["last_min"] = current_minute
                    API_USAGE[key]["min_count"] = 0
                
                # Reset Day count if day changed
                if API_USAGE[key]["last_day"] != current_day:
                    API_USAGE[key]["last_day"] = current_day
                    API_USAGE[key]["day_count"] = 0

                # Logic: Per Minute < 40 AND Per Day < 40
                if API_USAGE[key]["min_count"] < 40 and API_USAGE[key]["day_count"] < 40:
                    selected_key = key
                    selected_index = i + 1
                    API_USAGE[key]["min_count"] += 1
                    API_USAGE[key]["day_count"] += 1
                    break

            if not selected_key:
                self.send_error_response(429, "All API keys reached their daily or minute limit (40/40). Try again later.")
                return

            # 4. Prepare Messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.extend(history)
            if user_msg:
                messages.append({"role": "user", "content": user_msg})

            # 5. Call SambaNova API
            payload = {
                "model": "DeepSeek-R1-Distill-Llama-70B",
                "messages": messages,
                "temperature": 0.1,
                "top_p": 0.1
            }

            headers = {
                "Authorization": f"Bearer {selected_key}",
                "Content-Type": "application/json"
            }

            response = requests.post(
                "https://api.sambanova.ai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )

            # 6. Send Response
            self.send_response(response.status_code)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            if response.status_code == 200:
                result = response.json()
                result["api_info"] = {
                    "key_index": selected_index,
                    "day_usage": API_USAGE[selected_key]["day_count"]
                }
                self.wfile.write(json.dumps(result).encode())
            else:
                self.wfile.write(response.content)

        except Exception as e:
            self.send_error_response(500, f"Server Error: {str(e)}")

    def send_error_response(self, code, message):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())
