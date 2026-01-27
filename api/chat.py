from http.server import BaseHTTPRequestHandler
import json
import requests
import os
from datetime import datetime

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # 1. Input parsing
        content_length = int(self.headers['Content-Length'])
        post_data = json.loads(self.rfile.read(content_length))
        
        user_msg = post_data.get('message', '') # Default to empty string if missing
        image_url = post_data.get('image_url')  # New field for Image URL
        system_prompt = post_data.get('system', 'You are a helpful assistant.')
        history = post_data.get('history', [])

        # 2. Key Rotation Logic (Firebase) - SAME AS BEFORE
        all_keys = os.environ.get("MY_API_KEYS", "").split(",")
        FIREBASE_DB = "https://bol-ai-d94f4-default-rtdb.firebaseio.com"
        
        current_minute = datetime.now().strftime("%Y%m%d%H%M")
        selected_key = None
        selected_index = 0

        for i, key in enumerate(all_keys):
            usage_ref = f"{FIREBASE_DB}/api_usage/key_{i}/{current_minute}.json"
            try:
                usage_res = requests.get(usage_ref).json()
                count = usage_res if usage_res is not None else 0
            except:
                count = 0
            
            if count < 5:
                selected_key = key
                selected_index = i + 1
                requests.put(usage_ref, data=json.dumps(count + 1))
                break

        if not selected_key:
            self.send_response(429)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Exhausted"}).encode())
            return

        # 3. Message Construction (Updated for Multimodal/Image)
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)

        # Check if an image is provided
        if image_url:
            # Multimodal format
            user_content = [
                {
                    "type": "text",
                    "text": user_msg
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": image_url
                    }
                }
            ]
            messages.append({"role": "user", "content": user_content})
        else:
            # Standard text format
            messages.append({"role": "user", "content": user_msg})

        try:
            # 4. API Call (Updated Headers & Model)
            ai_res = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {selected_key}",
                    "Content-Type": "application/json"
                    # Removed HTTP-Referer and X-Title as requested
                },
                data=json.dumps({
                    "model": "google/gemma-3-27b-it:free", # Updated Model
                    "messages": messages
                })
            )
            
            # Handle non-200 API errors
            if ai_res.status_code != 200:
                self.send_response(ai_res.status_code)
                self.end_headers()
                self.wfile.write(ai_res.content)
                return

            data = ai_res.json()
            data["api_index"] = selected_index

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
            
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
