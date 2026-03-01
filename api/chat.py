from http.server import BaseHTTPRequestHandler
import json
import requests
import os
from datetime import datetime

# Bhava, apun ek global dabba (dictionary) banvlay jyat sagla hishob rahil
# Hya madhe aplya keys chi daily, hourly, minutely ani "per day 1M token" chi limit track hoil
API_CHA_HISHOB = {}

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # 1. Pahile check karuya apun la client kadhun data aalay ki nai
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_error_response(400, "Bhau, data tar de!")
                return

            post_data = json.loads(self.rfile.read(content_length))
            user_msg = post_data.get('message', '')
            system_prompt = post_data.get('system', "")
            history = post_data.get('history',[])

            # 2. Vercel madhun aplya saglya keys gheu (CEREBRAS_API_KEY_vivek)
            # Keys apun comma (,) deun save kelyat: "key1,key2,key3"
            all_keys_str = os.environ.get("CEREBRAS_API_KEY_vivek", "")
            all_keys =[k.strip() for k in all_keys_str.split(",") if k.strip()]
            
            if not all_keys:
                self.send_error_response(500, "Are bhava, API keys naiye env madhe! Set kar pahile.")
                return

            # 3. Aajcha time ani date kadhun gheu, mhanje limits set karta yetil
            now = datetime.now()
            current_min = now.strftime("%Y-%m-%d %H:%M")
            current_hour = now.strftime("%Y-%m-%d %H")
            current_day = now.strftime("%Y-%m-%d")

            selected_key = None
            
            # 4. Aata ek ek key check karuya, jyachi limit baki ahe ti key gheu
            for key in all_keys:
                # Jar key aplya hishob madhe nassel, tar tila add karuya (survatila)
                if key not in API_CHA_HISHOB:
                    API_CHA_HISHOB[key] = {
                        "min": current_min, "min_calls": 0,
                        "hour": current_hour, "hour_calls": 0,
                        "day": current_day, "day_calls": 0,
                        "day_tokens": 0 # PER DAY 1 Million token track karnyasathi
                    }
                    
                stats = API_CHA_HISHOB[key]
                
                # Time change zala ki junya limit che counter zero (0) karuya
                if stats["min"] != current_min:
                    stats["min"] = current_min
                    stats["min_calls"] = 0
                    
                if stats["hour"] != current_hour:
                    stats["hour"] = current_hour
                    stats["hour_calls"] = 0
                    
                if stats["day"] != current_day:
                    stats["day"] = current_day
                    stats["day_calls"] = 0
                    stats["day_tokens"] = 0 # Navin divas, navin 1 million limit!
                    
                # Aata main cheking! (60/min, 900/hr, 14400/day ani PER DAY 1 Million Tokens)
                if (stats["min_calls"] < 60 and 
                    stats["hour_calls"] < 900 and 
                    stats["day_calls"] < 14400 and 
                    stats["day_tokens"] < 1000000): # Divsala 1M Token check
                    
                    # Sagla barobar ahe, tar hi key lock karuya
                    selected_key = key
                    
                    # Key use keli mhanun hishob vadhvuya
                    stats["min_calls"] += 1
                    stats["hour_calls"] += 1
                    stats["day_calls"] += 1
                    break

            # Jar eka pan key chi limit baki nassel, tar error deu
            if not selected_key:
                self.send_error_response(429, "Bhaava, aplya saglya keys chi limit sampli ahe (Tokens kivha Time limit full zhaliye). Dusri navin key tak kivha udya try kar!")
                return

            # 5. Message ready karuya Cerebras la pathavnya sathi
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(history)
            if user_msg:
                messages.append({"role": "user", "content": user_msg})

            # 6. Cerebras API la call maruya
            url = "https://api.cerebras.ai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {selected_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "llama3.1-8b", # Tula jo model hava to thev
                "messages": messages,
                "max_completion_tokens": 8192,
                "temperature": 1,
                "top_p": 1,
                "stream": False # Tokens count karayche ahet mhanun stream band thevlay
            }

            ai_res = requests.post(url, headers=headers, json=payload)

            if ai_res.status_code == 200:
                data = ai_res.json()
                
                # 7. Token cha hishob update karuya (Input + Output = Total Tokens)
                total_tokens_used = data.get("usage", {}).get("total_tokens", 0)
                API_CHA_HISHOB[selected_key]["day_tokens"] += total_tokens_used

                # Response client la pathvuya
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())
            else:
                # API ne kahi lafda kela tar direct tich error pathvuya
                self.send_response(ai_res.status_code)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(ai_res.content)

        except Exception as e:
            # Code phatla tar hi error disel
            self.send_error_response(500, f"Kahitari vanda zala bhaava: {str(e)}")

    def send_error_response(self, code, message):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())
