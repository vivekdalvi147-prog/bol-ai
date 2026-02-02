from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import requests
import os
from datetime import datetime

# # API वापर ट्रॅक करण्यासाठी ग्लोबल शब्दकोश (Global Dictionary)
# # Format: { "key": {"day": "YYYY-MM-DD", "day_count": 0, "day_tokens": 0, "min": "YYYY-MM-DD HH:MM", "min_count": 0, "min_tokens": 0} }
API_USAGE = {}

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # 1. # इनपुट डेटा पार्स करा (Parse Input Data)
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_error_response(400, "No data received")
                return

            post_data = json.loads(self.rfile.read(content_length))
            user_msg = post_data.get('message')
            system_prompt = post_data.get('system', "You are a helpful assistant.")
            history = post_data.get('history', [])

            # 2. # Environment मधून API Keys मिळवा (Get API Keys)
            all_keys = os.environ.get("MY_API_KEYS", "").split(",")
            all_keys = [k.strip() for k in all_keys if k.strip()]
            
            if not all_keys:
                self.send_error_response(500, "No API Keys found in environment")
                return

            # 3. # वेळ ट्रॅकिंग (Time Tracking)
            now = datetime.now()
            current_minute = now.strftime("%Y-%m-%d %H:%M")
            current_day = now.strftime("%Y-%m-%d")

            selected_key = None
            selected_index = 0

            # 4. # Key रोटेशन आणि रेट लिमिटिंग लॉजिक (Key Rotation & Rate Limiting)
            for i, key in enumerate(all_keys):
                if key not in API_USAGE:
                    # # नवीन Key साठी डेटा तयार करा
                    API_USAGE[key] = {
                        "day": current_day, 
                        "day_count": 0, 
                        "day_tokens": 0, # # दिवसभराचे टोकन्स
                        "min": current_minute, 
                        "min_count": 0,
                        "min_tokens": 0  # # मिनिटाचे टोकन्स
                    }

                stats = API_USAGE[key]

                # # मिनिट बदलला असेल तर मिनिटाचा काउंट आणि टोकन्स रीसेट करा (Reset Minute Count & Tokens)
                if stats["min"] != current_minute:
                    stats["min"] = current_minute
                    stats["min_count"] = 0
                    stats["min_tokens"] = 0

                # # दिवस बदलला असेल तर दिवसाचा काउंट आणि टोकन्स रीसेट करा (Reset Day Count & Tokens)
                if stats["day"] != current_day:
                    stats["day"] = current_day
                    stats["day_count"] = 0
                    stats["day_tokens"] = 0

                # # लिमिट तपासा (Check Limits):
                # # 30 कॉल/मिनिट, 14400 कॉल/दिवस
                # # 15k टोकन्स/मिनिट, 500k टोकन्स/दिवस
                if (stats["min_count"] < 30 and 
                    stats["day_count"] < 14400 and
                    stats["min_tokens"] < 15000 and 
                    stats["day_tokens"] < 500000):
                    
                    selected_key = key
                    selected_index = i + 1
                    break

            if not selected_key:
                self.send_error_response(429, "Rate Limit Exceeded: All keys are exhausted (RPM, RPD, TPM, or TPD limit reached).")
                return

            # 5. # चॅट मेसेज तयार करा (Prepare Messages)
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(history)
            messages.append({"role": "user", "content": user_msg})

            # 6. # Groq API ला कॉल करा (Call Groq API)
            groq_url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {selected_key}",
                "Content-Type": "application/json"
            }
            
            # # नवीन मॉडेल (New Model)
            payload = {
                "model": "meta-llama/llama-guard-4-12b",
                "messages": messages,
                "temperature": 0.7
            }

            ai_res = requests.post(groq_url, headers=headers, json=payload)
            
            if ai_res.status_code == 200:
                data = ai_res.json()
                
                # # वापरलेले टोकन्स मोजा (Calculate Used Tokens)
                usage = data.get("usage", {})
                total_tokens = usage.get("total_tokens", 0)

                # # वापरातील आकडेवारी अपडेट करा (Update Usage Stats)
                API_USAGE[selected_key]["min_count"] += 1
                API_USAGE[selected_key]["day_count"] += 1
                API_USAGE[selected_key]["min_tokens"] += total_tokens
                API_USAGE[selected_key]["day_tokens"] += total_tokens

                # # रिस्पॉन्समध्ये माहिती जोडा (Add Metadata)
                data["api_usage_info"] = {
                    "key_index": selected_index,
                    "min_calls_remaining": 30 - API_USAGE[selected_key]["min_count"],
                    "min_tokens_remaining": 15000 - API_USAGE[selected_key]["min_tokens"]
                }

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())
            else:
                # # API एरर हँडल करा (Handle API Errors)
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

# # सर्व्हर लोकलवर चालवण्यासाठी (For local testing)
if __name__ == "__main__":
    port = 8000
    server = HTTPServer(('localhost', port), handler)
    print(f"Server started on port {port}")
    server.serve_forever()
