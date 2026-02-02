from http.server import BaseHTTPRequestHandler
import json
import requests
import os
from datetime import datetime

API_USAGE = {}

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "No data received"}).encode())
                return

            post_data = json.loads(self.rfile.read(content_length))
            
            user_msg = post_data.get('message')
            system_prompt = post_data.get('system')
            history = post_data.get('history', [])

            all_keys = os.environ.get("MY_INFORMATION_AI_BOL_AI", "").split(",")
            
            if not all_keys or all_keys == ['']:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "No API Keys found in environment"}).encode())
                return

            # Current Time Settings
            now = datetime.now()
            current_minute = now.strftime("%Y-%m-%d %H:%M")
            current_day = now.strftime("%Y-%m-%d")
            
            selected_key = None
            selected_index = 0
            reason_for_fail = "All API keys are currently at limit."

            for i, key in enumerate(all_keys):
                key = key.strip() 
                if not key: continue

                # Initialize key usage if not exists
                if key not in API_USAGE:
                    API_USAGE[key] = {
                        "minute_time": current_minute,
                        "minute_count": 0,
                        "daily_date": current_day,
                        "daily_count": 0
                    }

                # Reset Daily Count if date changed
                if API_USAGE[key]["daily_date"] != current_day:
                    API_USAGE[key]["daily_date"] = current_day
                    API_USAGE[key]["daily_count"] = 0

                # Reset Minute Count if minute changed
                if API_USAGE[key]["minute_time"] != current_minute:
                    API_USAGE[key]["minute_time"] = current_minute
                    API_USAGE[key]["minute_count"] = 0

                # --- CHECK LIMITS ---
                # 1. Per Day Limit (50)
                if API_USAGE[key]["daily_count"] >= 50:
                    reason_for_fail = "Daily limit (50 calls) reached for all keys."
                    continue 

                # 2. Per Minute Limit (5)
                if API_USAGE[key]["minute_count"] >= 5:
                    reason_for_fail = "Minute limit (5 calls) reached. Please wait a moment."
                    continue

                # If both checks pass, select this key
                selected_key = key
                selected_index = i + 1
                
                # Increment both counters
                API_USAGE[key]["minute_count"] += 1
                API_USAGE[key]["daily_count"] += 1
                break 

            if not selected_key:
                self.send_response(429) 
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "error": f"Server Busy: {reason_for_fail}"
                }).encode())
                return

            # API Call to OpenRouter
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(history)
            messages.append({"role": "user", "content": user_msg})

            ai_res = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {selected_key}",
                    "Content-Type": "application/json"
                },
                data=json.dumps({
                    "model": "arcee-ai/trinity-large-preview:free",
                    "messages": messages,
                    "reasoning": {"enabled": True}
                })
            )
            
            if ai_res.status_code == 200:
                data = ai_res.json()
                # Metadata for debugging limits
                data["api_index"] = f"Key-{selected_index}" 
                data["usage_stats"] = {
                    "today_total": API_USAGE[selected_key]["daily_count"],
                    "this_minute": API_USAGE[selected_key]["minute_count"]
                }

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())
            else:
                self.send_response(ai_res.status_code)
                self.end_headers()
                self.wfile.write(ai_res.content)

        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Internal Server Error: {str(e)}"}).encode())
