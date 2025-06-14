from flask import Flask, request, jsonify
import requests
import os
import json
import logging
import re
from datetime import datetime
from twilio.rest import Client
from knowledge import get_knowledge_context, load_knowledge, add_update  # Pastikan import benar

app = Flask(__name__)

# Konfigurasi
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE = "whatsapp:+14155238886"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ADMIN_PHONES = json.loads(os.getenv("ADMIN_PHONES", "[]"))
SANDBOX_CODE = os.getenv("SANDBOX_CODE", "default-code")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inisialisasi klien Twilio
try:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    logger.info("Twilio client initialized successfully")
except Exception as e:
    logger.error(f"Twilio init error: {str(e)}")
    twilio_client = None

def generate_ai_response(user_message, from_number):
    """Mengirim permintaan ke Groq API"""
    # Periksa perintah admin khusus
    if from_number in ADMIN_PHONES and user_message.startswith("/update "):
        new_info = user_message.replace("/update ", "")
        add_update(new_info)
        return f"✅ Update berhasil: {new_info}"
    
    # Jawaban untuk pertanyaan umum
    common_responses = {
        "halo": "Halo! Ada yang bisa saya bantu seputar DISNAKER Bartim?",
        "jam buka": "Jam pelayanan: Senin-Kamis 08.00-14.00 WIB | Jumat 08.00-11.00 WIB",
        "alamat": "Kantor DISNAKER Bartim: Jl. Tjilik Riwut KM 5, Tamiang Layang",
        "kartu kuning": "Syarat kartu kuning:\n1. Fotokopi KTP\n2. Pas foto 3x4\n3. Surat pengantar kelurahan",
        "pelatihan": "Program pelatihan gratis: Teknisi HP, Menjahit, Las, Tata Rias"
    }
    
    # Cek pertanyaan umum
    user_message_lower = user_message.lower()
    for keyword, response in common_responses.items():
        if keyword in user_message_lower:
            return response
    
    # Gunakan Groq AI untuk pertanyaan lain
    return query_groq(user_message)

def query_groq(user_message):
    """Mengirim permintaan ke Groq API"""
    if not GROQ_API_KEY:
        return "Maaf, layanan AI sedang dalam pemeliharaan"
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "Anda asisten Dinas Tenaga Kerja Barito Timur. "
                    "Jawab pertanyaan dengan singkat (maks 3 kalimat). "
                    "Fokus pada layanan ketenagakerjaan. "
                    "Jika tidak tahu, sarankan hubungi 0538-1234567."
                )
            },
            {
                "role": "user",
                "content": user_message
            }
        ],
        "model": "mixtral-8x7b-32768",
        "temperature": 0.3,
        "max_tokens": 256,
        "stream": False
    }
    
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            return data['choices'][0]['message']['content']
        else:
            logger.error(f"Groq API error: {response.status_code} - {response.text}")
            return "Maaf, layanan AI sedang sibuk. Silakan coba lagi nanti."
            
    except Exception as e:
        logger.error(f"Groq API exception: {str(e)}")
        return "Layanan informasi sedang gangguan sementara"

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "service": "DISNAKER Bartim Chatbot",
        "version": "1.0"
    })

@app.route('/test')
def test_endpoint():
    return "Test endpoint working!", 200

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    """Endpoint utama untuk WhatsApp webhook"""
    try:
        # Handle verification request (GET)
        if request.method == 'GET':
            hub_mode = request.args.get('hub.mode')
            hub_token = request.args.get('hub.verify_token')
            hub_challenge = request.args.get('hub.challenge')
            
            if hub_mode == 'subscribe' and hub_token == SANDBOX_CODE:
                return hub_challenge, 200
            return "Verification failed", 403
        
        # Handle incoming message (POST)
        data = request.form
        incoming_msg = data.get('Body', '').strip()
        from_number = data.get('From', '').replace('whatsapp:', '')
        
        if not incoming_msg:
            return '', 200
        
        logger.info(f"Pesan masuk dari {from_number}: {incoming_msg}")
        
        # Process message
        bot_response = generate_ai_response(incoming_msg, from_number)
        
        # Send reply
        if twilio_client:
            twilio_client.messages.create(
                body=bot_response,
                from_=TWILIO_PHONE,
                to=f"whatsapp:{from_number}"
            )
            logger.info(f"Balasan terkirim ke {from_number}")
        else:
            logger.error("Twilio client not initialized")
        
        return '', 200
    
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
