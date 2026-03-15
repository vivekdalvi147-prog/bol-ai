from http.server import BaseHTTPRequestHandler
import json
import requests
import os
import time

USAGE_STATS = {}

def get_valid_key():
    keys_env = os.environ.get("CEREBRAS_API_KEY_vivek", "")
    if not keys_env:
        return None
    
    keys = [k.strip() for k in keys_env.split(",") if k.strip()]
    current_time = int(time.time())
    current_minute = current_time // 60
    current_hour = current_time // 3600
    current_day = current_time // 86400

    for key in keys:
        if key not in USAGE_STATS:
            USAGE_STATS[key] = {
                "minute": {"ts": current_minute, "count": 0},
                "hour": {"ts": current_hour, "count": 0},
                "day": {"ts": current_day, "count": 0}
            }
        
        stats = USAGE_STATS[key]
        
        if stats["minute"]["ts"] != current_minute:
            stats["minute"] = {"ts": current_minute, "count": 0}
        if stats["hour"]["ts"] != current_hour:
            stats["hour"] = {"ts": current_hour, "count": 0}
        if stats["day"]["ts"] != current_day:
            stats["day"] = {"ts": current_day, "count": 0}
        
        if stats["minute"]["count"] < 30 and stats["hour"]["count"] < 900 and stats["day"]["count"] < 14400:
            stats["minute"]["count"] += 1
            stats["hour"]["count"] += 1
            stats["day"]["count"] += 1
            return key
            
    return None

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_error_response(400, "No data")
                return

            post_data = json.loads(self.rfile.read(content_length))
            user_msg = post_data.get('message', '')
            system_prompt = post_data.get('system', "")
            history = post_data.get('history',[])
            is_stream = post_data.get('stream', True)

            api_key = get_valid_key()
            if not api_key:
                self.send_error_response(429, "Rate limit exceeded for all keys or API key missing")
                return

            messages =[]
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            if history:
                messages.extend(history)

            if user_msg:
                messages.append({"role": "user", "content": user_msg})

            url = "https://api.cerebras.ai/v1/chat/completions"

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": "qwen-3-235b-a22b-instruct-2507",
                "messages": messages,
                "stream": is_stream,
                "max_completion_tokens": post_data.get("max_completion_tokens", 1500),
                "temperature": post_data.get("temperature", 0.2),
                "top_p": post_data.get("top_p", 0.8)
            }

            ai_res = requests.post(url, headers=headers, json=payload, stream=is_stream)

            self.send_response(ai_res.status_code)
            for k, v in ai_res.headers.items():
                if k.lower() not in['transfer-encoding', 'content-encoding', 'content-length']:
                    self.send_header(k, v)
            self.end_headers()

            if is_stream:
                for chunk in ai_res.iter_content(chunk_size=8192):
                    if chunk:
                        self.wfile.write(chunk)
                        self.wfile.flush()
            else:
                self.wfile.write(ai_res.content)

        except Exception as e:
            self.send_error_response(500, str(e))

    def send_error_response(self, code, message):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())
