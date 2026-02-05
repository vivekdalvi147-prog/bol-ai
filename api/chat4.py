ekfrom http.server import BaseHTTPRequestHandler
import json
import requests
import os
from datetime import datetime
import random

# Global dictionary to store usage in memory
API_USAGE = {}

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # 1. Read Input Data
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "No data received"}).encode())
                return

            post_data = json.loads(self.rfile.read(content_length))
            
            # Extract Parameters (Only Prompt is required now)
            user_prompt = post_data.get('prompt')
            aspect_ratio = post_data.get('aspect_ratio', "1:1") # Default Square
            
            if not user_prompt:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing 'prompt' in request body"}).encode())
                return

            # 2. Get Keys from Environment Variable (MY_API)
            all_keys = os.environ.get("MY_API", "").split(",")
            
            if not all_keys or all_keys == ['']:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "No API Keys found in environment variable 'MY_API'"}).encode())
                return

            # 3. Rate Limiting Logic (Same as before)
            now = datetime.now()
            current_minute = now.strftime("%Y-%m-%d %H:%M")
            current_day = now.strftime("%Y-%m-%d")
            
            selected_key = None
            selected_index = 0
            reason_for_fail = "All API keys are currently at limit."

            for i, key in enumerate(all_keys):
                key = key.strip() 
                if not key: continue

                if key not in API_USAGE:
                    API_USAGE[key] = {"minute_time": current_minute, "minute_count": 0, "daily_date": current_day, "daily_count": 0}

                if API_USAGE[key]["daily_date"] != current_day:
                    API_USAGE[key]["daily_date"] = current_day
                    API_USAGE[key]["daily_count"] = 0

                if API_USAGE[key]["minute_time"] != current_minute:
                    API_USAGE[key]["minute_time"] = current_minute
                    API_USAGE[key]["minute_count"] = 0

                if API_USAGE[key]["daily_count"] >= 50:
                    reason_for_fail = "Daily limit (50 calls) reached."
                    continue 
                if API_USAGE[key]["minute_count"] >= 5:
                    reason_for_fail = "Minute limit (5 calls) reached."
                    continue

                selected_key = key
                selected_index = i + 1
                API_USAGE[key]["minute_count"] += 1
                API_USAGE[key]["daily_count"] += 1
                break 

            if not selected_key:
                self.send_response(429) 
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"Server Busy: {reason_for_fail}"}).encode())
                return

            # 4. Prepare API Call for NVIDIA Flux.1 Dev (Text to Image)
            invoke_url = "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-dev"

            headers = {
                "Authorization": f"Bearer {selected_key}",
                "Accept": "application/json",
                "Content-Type": "application/json"
            }

            # Handle Aspect Ratio to Width/Height
            width, height = 1024, 1024
            if aspect_ratio == "16:9":
                width, height = 1024, 576
            elif aspect_ratio == "9:16":
                width, height = 576, 1024

            payload = {
                "prompt": user_prompt,
                "width": width,
                "height": height,
                "steps": 28,
                "guidance_scale": 3.5,
                "seed": random.randint(0, 100000) # Random seed for new results every time
            }

            # 5. Make the Request
            ai_res = requests.post(invoke_url, headers=headers, json=payload)
            
            if ai_res.status_code == 200:
                data = ai_res.json()
                data["api_index"] = f"Key-{selected_index}" 
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
