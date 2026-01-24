from http.server import BaseHTTPRequestHandler
import json
import requests
import os
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore

if not firebase_admin._apps:
    try:
        service_account_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT')
        if service_account_json:
            service_account_info = json.loads(service_account_json)
            cred = credentials.Certificate(service_account_info)
            firebase_admin.initialize_app(cred)
    except:
        pass

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = json.loads(self.rfile.read(content_length).decode('utf-8'))
            
            user_msg = post_data.get('message')
            system_prompt = post_data.get('system')
            history = post_data.get('history', [])

            all_keys = [k.strip() for k in os.environ.get("MY_API_KEYS", "").split(",") if k.strip()]
            
            selected_key = all_keys[0] if all_keys else ""
            selected_index = 1
            
            try:
                if firebase_admin._apps:
                    db = firestore.client()
                    curr_min = datetime.now().strftime("%Y%m%d%H%M")
                    doc_ref = db.collection('api_usage').document(curr_min)
                    usage = doc_ref.get().to_dict() or {}
                    
                    for i, key in enumerate(all_keys):
                        if usage.get(f"key_{i}", 0) < 5:
                            selected_key = key
                            selected_index = i + 1
                            doc_ref.set({f"key_{i}": usage.get(f"key_{i}", 0) + 1}, merge=True)
                            break
            except:
                pass

            res = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {selected_key}", "Content-Type": "application/json"},
                json={"model": "xiaomi/mimo-v2-flash:free", "messages": [{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": user_msg}]}
            )
            
            data = res.json()
            data["api_index"] = selected_index
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode())
