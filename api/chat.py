from http.server import BaseHTTPRequestHandler
import json
import requests
import os
from datetime import datetime

# Global dictionary to track usage in memory (RAM)
# Iska structure aisa hoga:
# {
#    "sk-key1...": { "time": "2023-10-27 12:23", "count": 3 },
#    "sk-key2...": { "time": "2023-10-27 12:23", "count": 5 }
# }
API_USAGE = {}

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # 1. Input Data Read karna
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

            # 2. API Keys load karna (Environment Variable se)
            # Keys comma se separate honi chahiye (key1,key2,key3)
            all_keys = os.environ.get("MY_API_KEYS", "").split(",")
            
            # Agar keys empty hain to error do
            if not all_keys or all_keys == ['']:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "No API Keys found in environment"}).encode())
                return

            # Current minute nikalna (e.g., "2023-10-27 12:23")
            current_minute = datetime.now().strftime("%Y-%m-%d %H:%M")
            
            selected_key = None
            selected_index = 0

            # 3. Key Rotation aur Rate Limiting Logic (WITHOUT FIREBASE)
            # Hum har key ko check karenge
            for i, key in enumerate(all_keys):
                key = key.strip() # Spaces remove karna
                if not key: continue

                # Agar ye key pehli baar use ho rahi hai, to initialize kro
                if key not in API_USAGE:
                    API_USAGE[key] = {"time": current_minute, "count": 0}

                # Check kro ki kya minute badal gaya hai?
                # Agar last used time aur current time alag hai, to count reset karo (0)
                if API_USAGE[key]["time"] != current_minute:
                    API_USAGE[key]["time"] = current_minute
                    API_USAGE[key]["count"] = 0

                # Ab check kro limit (Max 5 requests per minute)
                if API_USAGE[key]["count"] < 5:
                    selected_key = key
                    selected_index = i + 1
                    
                    # Count badha do (Memory me update)
                    API_USAGE[key]["count"] += 1
                    break # Loop rok do, kyunki hume free key mil gayi

            # Agar saari keys exhaust (limit cross) ho gayi hain
            if not selected_key:
                self.send_response(429) # Too Many Requests
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "error": "Server Busy: All API keys are currently at limit. Please try again in 1 minute."
                }).encode())
                return

            # 4. Message History Prepare karna
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(history)
            messages.append({"role": "user", "content": user_msg})

            # 5. OpenRouter API Call
            ai_res = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {selected_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://bol-ai.vercel.app", # Apna URL yahan dalein
                    "X-Title": "Bol AI",
                },
                data=json.dumps({
                    "model": "tngtech/deepseek-r1t2-chimera:free", # Model name
                    "messages": messages
                })
            )
            
            # Response handling
            if ai_res.status_code == 200:
                data = ai_res.json()
                data["api_index"] = f"Key-{selected_index}" # Bataega kaunsi key use hui debug ke liye

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())
            else:
                # Agar API se error aaye (jaise ki key invalid ho)
                self.send_response(ai_res.status_code)
                self.end_headers()
                self.wfile.write(ai_res.content)

        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Internal Server Error: {str(e)}"}).encode())
