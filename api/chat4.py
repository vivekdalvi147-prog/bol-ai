from http.server import BaseHTTPRequestHandler
import json
import requests
import os
from datetime import datetime

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
            
            # Extract Image API Parameters
            # Client must send 'prompt' and 'image' (base64 string)
            user_prompt = post_data.get('prompt')
            input_image = post_data.get('image') 
            
            # Optional parameters with defaults
            aspect_ratio = post_data.get('aspect_ratio', "match_input_image")
            steps = post_data.get('steps', 30)
            cfg_scale = post_data.get('cfg_scale', 3.5)
            seed = post_data.get('seed', 0)

            if not user_prompt or not input_image:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing 'prompt' or 'image' in request body"}).encode())
                return

            # 2. Get Keys from Environment Variable (MY_API)
            all_keys = os.environ.get("MY_API", "").split(",")
            
            if not all_keys or all_keys == ['']:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "No API Keys found in environment variable 'MY_API'"}).encode())
                return

            # 3. Rate Limiting Logic (SAME AS OLD CODE)
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

            # 4. Prepare API Call for NVIDIA Flux
            invoke_url = "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-kontext-dev"

            headers = {
                "Authorization": f"Bearer {selected_key}",
                "Accept": "application/json",
                "Content-Type": "application/json"
            }

            payload = {
                "prompt": user_prompt,
                "image": input_image, # Needs to be proper Base64 string
                "aspect_ratio": aspect_ratio,
                "steps": steps,
                "cfg_scale": cfg_scale,
                "seed": seed
            }

            # 5. Make the Request
            ai_res = requests.post(invoke_url, headers=headers, json=payload)
            
            # 6. Handle Response
            if ai_res.status_code == 200:
                data = ai_res.json()
                
                # Add usage metadata
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
