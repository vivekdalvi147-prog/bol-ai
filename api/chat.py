# एक छोटं उदाहरण (Flask वापरून)
from flask import Flask, request, jsonify
import os
import openai

app = Flask(__name__)

@app.route('/get-response', methods=['POST'])
def get_ai_response():
    user_message = request.json.get('message')
    api_key = os.getenv("MY_API_KEY") # इथे तुमची की सुरक्षित राहील
    
    # AI ला कॉल करण्याची लॉजिक इथे येईल
    # response = call_ai_api(user_message, api_key)
    
    return jsonify({"response": "AI कडून आलेले उत्तर"})
