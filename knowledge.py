from flask import Flask, request, jsonify
import requests
import os
import re
import logging
from datetime import datetime

app = Flask(__name__)

# Konfigurasi
ADMIN_PHONE = "6285245407566"  # Nomor admin tanpa +
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database sementara (simpan di memory)
message_store = {}

@app.route('/relay', methods=['POST'])
def relay_handler():
    """Endpoint untuk menerima pesan dari admin (via WA Business)"""
    try:
        # Format: {"from": "628123456789", "text": "Pertanyaan..."}
        data = request.json
        sender = data['from']  # Nomor publik
        message = data['text']
        
        # Simpan ke store
        message_store[sender] = message
        
        # Teruskan ke Twilio sandbox
        relay_to_twilio(sender, message)
        
        return jsonify({"status": "relayed"}), 200
    
    except Exception as e:
        logger.error(f"Relay error: {str(e)}")
        return jsonify({"error": str(e)}), 500

def relay_to_twilio(sender, message):
    """Kirim pesan ke Twilio sandbox seolah dari admin"""
    payload = {
        "Body": f"{sender}: {message}",
        "From": f"whatsapp:+{ADMIN_PHONE}",
        "To": "whatsapp:+14155238886"  # Sandbox Twilio
    }
    
    try:
        response = requests.post(
            "https://api.twilio.com/2010-04-01/Accounts/<YOUR_TWILIO_SID>/Messages.json",
            auth=("<TWILIO_SID>", "<TWILIO_AUTH_TOKEN>"),
            data=payload
        )
        logger.info(f"Relay to Twilio: {response.status_code}")
    except Exception as e:
        logger.error(f"Twilio relay failed: {str(e)}")

@app.route('/webhook', methods=['POST'])
def webhook():
    """Webhook untuk Twilio sandbox (seperti biasa)"""
    try:
        incoming_msg = request.values.get('Body', '').strip()
        from_number = request.values.get('From', '').replace('whatsapp:', '')
        
        # Identifikasi pesan relay dari admin
        if from_number == ADMIN_PHONE and ':' in incoming_msg:
            match = re.match(r'(\d+):\s*(.+)', incoming_msg)
            if match:
                original_sender = match.group(1)  # Nomor publik
                original_message = match.group(2)
                
                # Proses dengan AI
                bot_response = generate_ai_response(original_message)
                
                # Format untuk admin
                formatted_response = f"🔔 Balas ke {original_sender}:\n{bot_response}"
                
                # Kirim ke admin
                send_to_admin(formatted_response)
                
                return '', 200
        
        # ... [kode bot normal lainnya] ...
    
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return jsonify({"error": str(e)}), 500

def generate_ai_response(message):
    """Generate response using Groq (sama seperti sebelumnya)"""
    # ... [implementasi Groq] ...
    return "Respon dari AI"

def send_to_admin(message):
    """Kirim pesan ke admin via WhatsApp Business API"""
    # Implementasi tergantung platform WA Business
    # Contoh menggunakan CallMeBot API (gratis)
    try:
        api_url = f"https://api.callmebot.com/whatsapp.php?phone={ADMIN_PHONE}&text={message}&apikey=<YOUR_API_KEY>"
        requests.get(api_url)
    except Exception as e:
        logger.error(f"Failed to notify admin: {str(e)}")
