from http.server import BaseHTTPRequestHandler
import json
import requests
import os
from datetime import datetime

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # 1. Input Parsing
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = json.loads(self.rfile.read(content_length))
            
            user_msg = post_data.get('message')
            system_prompt = post_data.get('system')
            # Frontend se jo history aayegi, usme "reasoning_details" hona chahiye 
            # agar pichla message assistant ka tha.
            history = post_data.get('history', []) 
        except Exception:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid request"}).encode())
            return

        # 2. Key Rotation Logic (Firebase)
        all_keys = os.environ.get("MY_API_KEYS", "").split(",")
        FIREBASE_DB = "https://bol-ai-d94f4-default-rtdb.firebaseio.com"
        
        current_minute = datetime.now().strftime("%Y%m%d%H%M")
        selected_key = None
        selected_index = 0

        # Simple logic to find a usable key
        for i, key in enumerate(all_keys):
            try:
                usage_ref = f"{FIREBASE_DB}/api_usage/key_{i}/{current_minute}.json"
                usage_res = requests.get(usage_ref).json()
                count = usage_res if usage_res is not None else 0
                
                if count < 5:
                    selected_key = key
                    selected_index = i + 1
                    requests.put(usage_ref, data=json.dumps(count + 1))
                    break
            except:
                continue # Agar firebase fail ho to next key try kare

        if not selected_key:
            self.send_response(429)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Exhausted"}).encode())
            return

        # 3. Message Construction
        # System prompt sabse pehle
        messages = [{"role": "system", "content": system_prompt}]
        
        # History add karein (Isme assistant ke 'reasoning_details' included hone chahiye frontend se)
        messages.extend(history)
        
        # Current user message
        messages.append({"role": "user", "content": user_msg})

        try:
            # 4. API Call (Updated Model & Reasoning Logic)
            ai_res = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {selected_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://bol-ai.vercel.app", 
                    "X-Title": "Bol AI",                         
                },
                data=json.dumps({
                    # NEW MODEL UPDATE
                    "model": "openai/gpt-oss-120b:free", 
                    "messages": messages,
                    # REASONING ENABLED
                    "reasoning": {"enabled": True} 
                })
            )
            
            data = ai_res.json()
            
            # Error handling agar OpenRouter se error aaye
            if "error" in data:
                raise Exception(data["error"].get("message", "Unknown OpenRouter Error"))

            data["api_index"] = selected_index

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
