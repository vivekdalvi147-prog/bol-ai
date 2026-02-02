from http.server import BaseHTTPRequestHandler
import json
import requests
import os
from datetime import datetime

# Global dictionary to track usage
# Format: { "key": {"day": "YYYY-MM-DD", "day_count": 0, "min": "YYYY-MM-DD HH:MM", "min_count": 0} }
API_USAGE = {}

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # 1. Parse Input Data
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_error_response(400, "No data received")
                return

            post_data = json.loads(self.rfile.read(content_length))
            user_msg = post_data.get('message')
            system_prompt = post_data.get('system', "You are a helpful assistant.")
            history = post_data.get('history', [])

            # 2. Get API Keys from Environment
            all_keys = os.environ.get("MY_API_KEYS", "").split(",")
            all_keys = [k.strip() for k in all_keys if k.strip()]
            
            if not all_keys:
                self.send_error_response(500, "No API Keys found in environment")
                return

            # 3. Time tracking for limits
            now = datetime.now()
            current_minute = now.strftime("%Y-%m-%d %H:%M")
            current_day = now.strftime("%Y-%m-%d")

            selected_key = None
            selected_index = 0

            # 4. Key Rotation & Rate Limiting Logic
            for i, key in enumerate(all_keys):
                if key not in API_USAGE:
                    API_USAGE[key] = {
                        "day": current_day, "day_count": 0,
                        "min": current_minute, "min_count": 0
                    }

                stats = API_USAGE[key]

                # Reset Minute Count if minute changed
                if stats["min"] != current_minute:
                    stats["min"] = current_minute
                    stats["min_count"] = 0

                # Reset Day Count if day changed
                if stats["day"] != current_day:
                    stats["day"] = current_day
                    stats["day_count"] = 0

                # Check Limits: 30 per minute AND 1000 per day
                if stats["min_count"] < 30 and stats["day_count"] < 1000:
                    selected_key = key
                    selected_index = i + 1
                    stats["min_count"] += 1
                    stats["day_count"] += 1
                    break

            if not selected_key:
                self.send_error_response(429, "Rate Limit Exceeded: All keys are busy (Max 30/min or 1000/day).")
                return

            # 5. Prepare Messages for Chat Completion
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(history)
            messages.append({"role": "user", "content": user_msg})

            # 6. Call Groq API (Kimi Model)
            # Note: Groq uses OpenAI compatible endpoint
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
                # Metadata add karna (kaunsa key use hua)
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
                # API error handles
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
