from http.server import BaseHTTPRequestHandler
import json
import os
import time
import redis
from cerebras.cloud.sdk import Cerebras

KV_URL = os.environ.get("KV_URL")
if KV_URL:
    kv = redis.from_url(KV_URL)
else:
    kv = None

API_KEYS = [
    value for key, value in os.environ.items() if key.startswith("CEREBRAS_API_KEY_")
]

MINUTE_LIMIT = 30
HOUR_LIMIT = 900
DAY_LIMIT = 14400

class handler(BaseHTTPRequestHandler):

    def get_available_key(self):
        if not kv:
            return API_KEYS[0] if API_KEYS else None

        now = time.time()
        for api_key in API_KEYS:
            key_identifier = f"rate_limit:{api_key[-4:]}"
            
            kv.zremrangebyscore(key_identifier, '-inf', now - 86400)

            minute_count = kv.zcount(key_identifier, now - 60, now)
            hour_count = kv.zcount(key_identifier, now - 3600, now)
            day_count = kv.zcount(key_identifier, now - 86400, now)

            if minute_count < MINUTE_LIMIT and hour_count < HOUR_LIMIT and day_count < DAY_LIMIT:
                return api_key
        return None

    def record_request(self, api_key):
        if not kv:
            return
            
        now = time.time()
        key_identifier = f"rate_limit:{api_key[-4:]}"
        kv.zadd(key_identifier, {str(now): now})


    def send_json_response(self, status_code, content):
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(content).encode('utf-8'))

    def do_POST(self):
        try:
            if not API_KEYS:
                self.send_json_response(500, {"error": "Cerebras API keys are not configured."})
                return

            if not kv:
                self.send_json_response(500, {"error": "Vercel KV (Redis) is not configured."})
                return

            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_json_response(400, {"error": "No data received"})
                return

            post_data = json.loads(self.rfile.read(content_length))
            user_msg = post_data.get('message', '')
            system_prompt = post_data.get('system', "")
            history = post_data.get('history', [])

            selected_api_key = self.get_available_key()

            if not selected_api_key:
                self.send_json_response(429, {"error": "All API keys are rate-limited. Please try again later."})
                return
            
            client = Cerebras(api_key=selected_api_key, api_url="https://api.cerebras.ai/v1/chat/completions")

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            messages.extend(history)
            
            if user_msg:
                messages.append({"role": "user", "content": user_msg})
            
            if not messages:
                 self.send_json_response(400, {"error": "No message to process."})
                 return

            stream = client.chat.completions.create(
                model="qwen-3-235b-a22b-instruct-2507",
                messages=messages,
                stream=True,
                max_completion_tokens=1500,
                temperature=0.2,
                top_p=0.8
            )

            full_response_content = ""
            for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    full_response_content += content
            
            self.record_request(selected_api_key)

            final_data = {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": full_response_content
                    }
                }]
            }

            self.send_json_response(200, final_data)

        except json.JSONDecodeError:
            self.send_json_response(400, {"error": "Invalid JSON format."})
        except Exception as e:
            self.send_json_response(500, {"error": str(e)})
