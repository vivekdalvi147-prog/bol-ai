from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app) # यामुळे तुमची HTML वेबसाईट याला कॉल करू शकेल

# तुमची API Key GitHub Secrets किंवा Environment Variables मधून येईल
API_KEY = os.getenv("OPENROUTER_API_KEY")

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get("message")
    system_prompt = data.get("system", "You are bol.ai, built by Vivek Dalvi.")
    context = data.get("context", [])

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "xiaomi/mimo-v2-flash:free",
        "messages": [
            {"role": "system", "content": system_prompt},
            *context,
            {"role": "user", "content": user_message}
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
