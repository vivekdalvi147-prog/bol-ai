from http.server import BaseHTTPRequestHandler
import json
import requests
import os
from datetime import datetime

# Global dictionary to track API usage per key
API_USAGE = {}

class handler(BaseHTTPRequestHandler):
    
    # CORS Headers handle karne ke liye (Frontend se error nahi aayega)
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def do_POST(self):
        try:
            # 1. Content Length Check
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "No data received"}).encode())
                return

            # 2. Parse Incoming Data
            post_data = json.loads(self.rfile.read(content_length))
            
            user_msg = post_data.get('message')
            system_prompt = post_data.get('system', "You are a helpful assistant.") # Default system prompt
            history = post_data.get('history', [])

            if not user_msg and not history:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Message content is required"}).encode())
                return

            # 3. Get API Keys from Environment Variable (MY_CODER_API)
            all_keys_str = os.environ.get("MY_CODER_API", "")
            all_keys = [k.strip() for k in all_keys_str.split(",") if k.strip()]
            
            if not all_keys:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "No API Keys found in MY_CODER_API environment"}).encode())
                return

            # 4. Key Selection Logic (Rate Limiting)
            current_minute = datetime.now().strftime("%Y-%m-%d %H:%M")
            selected_key = None
            selected_index = 0

            for i, key in enumerate(all_keys):
                if key not in API_USAGE:
                    API_USAGE[key] = {"time": current_minute, "count": 0}

                # Reset count if minute changed
                if API_USAGE[key]["time"] != current_minute:
                    API_USAGE[key]["time"] = current_minute
                    API_USAGE[key]["count"] = 0

                # Check limit (5 requests per minute per key)
                if API_USAGE[key]["count"] < 5:
                    selected_key = key
                    selected_index = i + 1
                    API_USAGE[key]["count"] += 1
                    break 

            if not selected_key:
                self.send_response(429) 
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "error": "Server Busy: All API keys are currently at limit. Please try again in 1 minute."
                }).encode())
                return

            # 5. Prepare Messages for OpenRouter
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            messages.extend(history)
            
            if user_msg:
                messages.append({"role": "user", "content": user_msg})

            # 6. Call OpenRouter API with NEW MODEL
            ai_res = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {selected_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://bol-ai.vercel.app", # Apna URL yahan update kar sakte ho
                    "X-Title": "Bol AI",
                },
                data=json.dumps({
                    "model": "deepseek/deepseek-r1-0528:free", # Updated Model Name
                    "messages": messages
                })
            )
            
            # 7. Send Response back to Client
            self.send_response(ai_res.status_code)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*') # CORS Header
            self.end_headers()

            if ai_res.status_code == 200:
                data = ai_res.json()
                data["api_index"] = f"Key-{selected_index}" # Debugging ke liye
                self.wfile.write(json.dumps(data).encode())
            else:
                self.wfile.write(ai_res.content)

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Internal Server Error: {str(e)}"}).encode())
