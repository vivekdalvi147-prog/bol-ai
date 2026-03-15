from http.server import BaseHTTPRequestHandler
import json
import os
import time
from cerebras.cloud.sdk import Cerebras
from collections import defaultdict

class ApiKeyManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ApiKeyManager, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def initialize(self):
        if self.initialized:
            return

        self.api_keys = []
        i = 1
        while True:
            key = os.environ.get(f"Api{i}")
            if key:
                self.api_keys.append(key)
                i += 1
            else:
                break
        
        self.api_usage = defaultdict(lambda: {"timestamps": []})
        self.RATE_LIMITS = {
            "minute": (30, 60),
            "hour": (900, 3600),
            "day": (14400, 86400)
        }
        self.initialized = True

    def get_available_key(self):
        now = time.time()
        
        for key in self.api_keys:
            timestamps = self.api_usage[key]["timestamps"]
            
            self.api_usage[key]["timestamps"] = [t for t in timestamps if now - t < self.RATE_LIMITS["day"][1]]
            
            recent_timestamps = self.api_usage[key]["timestamps"]
            
            minute_count = sum(1 for t in recent_timestamps if now - t < self.RATE_LIMITS["minute"][1])
            hour_count = sum(1 for t in recent_timestamps if now - t < self.RATE_LIMITS["hour"][1])
            day_count = len(recent_timestamps)
            
            if (minute_count < self.RATE_LIMITS["minute"][0] and
                hour_count < self.RATE_LIMITS["hour"][0] and
                day_count < self.RATE_LIMITS["day"][0]):
                return key
        
        return None

    def record_usage(self, key):
        self.api_usage[key]["timestamps"].append(time.time())

class handler(BaseHTTPRequestHandler):
    
    key_manager = ApiKeyManager()

    def do_POST(self):
        try:
            self.key_manager.initialize()

            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_error_response(400, "Request body is empty")
                return

            post_data = json.loads(self.rfile.read(content_length))
            user_msg = post_data.get('message', '')
            system_prompt = post_data.get('system', "")
            history = post_data.get('history', [])

            available_key = self.key_manager.get_available_key()

            if not available_key:
                self.send_error_response(429, "All API keys have reached their rate limits.")
                return

            client = Cerebras(api_key=available_key, api_url="https://api.cerebras.ai/v1")

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            if history:
                messages.extend(history)
            
            if user_msg:
                messages.append({"role": "user", "content": user_msg})
            else:
                self.send_error_response(400, "User message is missing")
                return

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            stream = client.chat.completions.create(
                model="qwen-3-235b-a22b-instruct-2507",
                messages=messages,
                stream=True,
                max_completion_tokens=1500,
                temperature=0.2,
                top_p=0.8
            )

            for chunk in stream:
                content = chunk.choices[0].delta.content or ""
                if content:
                    self.wfile.write(content.encode('utf-8'))
            
            self.key_manager.record_usage(available_key)

        except json.JSONDecodeError:
            self.send_error_response(400, "Invalid JSON format")
        except Exception as e:
            self.send_error_response(500, str(e))

    def send_error_response(self, code, message):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode('utf-8'))
