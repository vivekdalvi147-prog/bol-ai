from http.server import BaseHTTPRequestHandler
import json
import os
from datetime import datetime
from google import genai
from google.genai import types

# Global Dictionary to track usage
# Format: { "API_KEY": {"min": "HH:MM", "min_req": 0, "min_tokens": 0, "day": "YYYY-MM-DD", "day_req": 0} }
API_USAGE = {}

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_error_res(400, "No data received")
                return

            post_data = json.loads(self.rfile.read(content_length))
            user_msg = post_data.get('message')
            system_prompt = post_data.get('system', "You are a helpful assistant.")
            history = post_data.get('history', [])

            # Load API Keys from Environment
            all_keys = os.environ.get("MY_CODER_BOL_AI", "").split(",")
            all_keys = [k.strip() for k in all_keys if k.strip()]

            if not all_keys:
                self.send_error_res(500, "No API Keys found in environment variable MY_CODER_BOL_AI")
                return

            now = datetime.now()
            current_minute = now.strftime("%Y-%m-%d %H:%M")
            current_day = now.strftime("%Y-%m-%d")

            selected_key = None
            selected_index = 0

            # Logic to find available key based on limits
            for i, key in enumerate(all_keys):
                if key not in API_USAGE:
                    API_USAGE[key] = {
                        "min": current_minute, "min_req": 0, "min_tokens": 0,
                        "day": current_day, "day_req": 0
                    }

                # Reset Minute Limits if minute changed
                if API_USAGE[key]["min"] != current_minute:
                    API_USAGE[key]["min"] = current_minute
                    API_USAGE[key]["min_req"] = 0
                    API_USAGE[key]["min_tokens"] = 0

                # Reset Daily Limits if day changed
                if API_USAGE[key]["day"] != current_day:
                    API_USAGE[key]["day"] = current_day
                    API_USAGE[key]["day_req"] = 0

                # Check Constraints: 30 requests/min, 14000 requests/day, 15000 tokens/min
                if (API_USAGE[key]["min_req"] < 30 and 
                    API_USAGE[key]["day_req"] < 14000 and 
                    API_USAGE[key]["min_tokens"] < 15000):
                    
                    selected_key = key
                    selected_index = i + 1
                    break

            if not selected_key:
                self.send_error_res(429, "All API keys reached their limit (RPM/TPM/RPD). Try again later.")
                return

            # Initialize Google GenAI Client
            client = genai.Client(api_key=selected_key)

            # Format History for Gemini (User/Model roles)
            # GenAI uses 'user' and 'model'
            formatted_contents = []
            for h in history:
                role = "model" if h['role'] == "assistant" else "user"
                formatted_contents.append(types.Content(role=role, parts=[types.Part.from_text(text=h['content'])]))
            
            # Add current user message
            formatted_contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_msg)]))

            # Call API
            response = client.models.generate_content(
                model="gemma-3-27b",
                contents=formatted_contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=1000 # Aap ise adjust kar sakte hain
                )
            )

            # Extract Token Usage
            usage = response.usage_metadata
            total_tokens = usage.total_token_count if usage else 0

            # Update Usage Stats
            API_USAGE[selected_key]["min_req"] += 1
            API_USAGE[selected_key]["day_req"] += 1
            API_USAGE[selected_key]["min_tokens"] += total_tokens

            # Send Success Response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            final_res = {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": response.text
                    }
                }],
                "usage": {
                    "total_tokens": total_tokens,
                    "prompt_tokens": usage.prompt_token_count if usage else 0,
                    "completion_tokens": usage.candidates_token_count if usage else 0
                },
                "api_index": f"Key-{selected_index}",
                "model": "gemma-3-27b"
            }
            self.wfile.write(json.dumps(final_res).encode())

        except Exception as e:
            self.send_error_res(500, f"Error: {str(e)}")

    def send_error_res(self, code, message):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())
