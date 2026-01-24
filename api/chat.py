from http.server import BaseHTTPRequestHandler
import json
import requests
import os
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore

# --- FIREBASE ADMIN INITIALIZATION (Singleton Pattern) ---
# Vercel environment variable 'FIREBASE_SERVICE_ACCOUNT' must contain the JSON content
if not firebase_admin._apps:
    try:
        # Load credentials from Environment Variable (Best for Vercel)
        service_account_info = json.loads(os.environ.get('FIREBASE_SERVICE_ACCOUNT', '{}'))
        cred = credentials.Certificate(service_account_info)
        firebase_admin.initialize_app(cred)
    except Exception as e:
        print(f"Firebase Init Error: {e}")

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # 1. Parse Input
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = json.loads(self.rfile.read(content_length))
        except:
            self.send_error(400, "Invalid JSON")
            return
        
        user_msg = post_data.get('message')
        system_prompt = post_data.get('system')
        history = post_data.get('history', [])

        # 2. Get API Keys
        all_keys = os.environ.get("MY_API_KEYS", "").split(",")
        if not all_keys or all_keys == ['']:
            self._send_json(500, {"error": "Server Configuration Error: No API Keys found"})
            return

        # 3. Rate Limiting Logic (Firestore)
        db = firestore.client()
        current_minute = datetime.now().strftime("%Y%m%d%H%M") # E.g., 202601242044
        doc_ref = db.collection('api_usage').document(current_minute)
        
        selected_key = None
        selected_index = 0

        try:
            # Transaction ensures atomic reads/writes
            @firestore.transactional
            def get_available_key(transaction, doc_ref):
                snapshot = transaction.get(doc_ref)
                usage_data = snapshot.to_dict() if snapshot.exists else {}
                
                found_key = None
                found_idx = 0

                for i, key in enumerate(all_keys):
                    key_id = f"key_{i}"
                    current_count = usage_data.get(key_id, 0)
                    
                    if current_count < 5:
                        # Found a free key, increment count
                        transaction.set(doc_ref, {key_id: current_count + 1}, merge=True)
                        found_key = key
                        found_idx = i + 1
                        break
                
                return found_key, found_idx

            transaction = db.transaction()
            selected_key, selected_index = get_available_key(transaction, doc_ref)

        except Exception as e:
            # Fallback if Firestore fails (allow request purely on rotation to avoid downtime)
            print(f"Firestore Error: {e}")
            selected_key = all_keys[0]
            selected_index = 1

        if not selected_key:
            self._send_json(429, {"error": "All Server Nodes Busy. Please wait 1 minute."})
            return

        # 4. Prepare AI Request
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_msg})

        try:
            ai_res = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {selected_key}", 
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://bol-ai.vercel.app", # Required by OpenRouter
                    "X-Title": "Bol-AI"
                },
                data=json.dumps({
                    "model": "xiaomi/mimo-v2-flash:free", 
                    "messages": messages
                })
            )
            
            if ai_res.status_code != 200:
                self._send_json(ai_res.status_code, {"error": f"Upstream Error: {ai_res.text}"})
                return

            data = ai_res.json()
            
            # Append which server node was used
            data["api_index"] = selected_index
            
            self._send_json(200, data)

        except Exception as e:
            self._send_json(500, {"error": str(e)})

    def _send_json(self, status, data):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*') # CORS Support
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
