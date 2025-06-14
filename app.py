from flask import Flask, request, jsonify
import requests
import os
import json
import logging
from datetime import datetime
from twilio.rest import Client
from knowledge import get_knowledge_context, load_knowledge, add_update

app = Flask(__name__)

# Konfigurasi
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE = "whatsapp:+14155238886"  # Sandbox number
GROQ_API_KEY = os.getenv("GROQ_API_KEY")  # Ganti ke Groq
ADMIN_PHONES = json.loads(os.getenv("ADMIN_PHONES", "[]"))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inisialisasi klien Twilio
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

def generate_ai_response(user_message, from_number):
    """Mengirim permintaan ke Groq API"""
    # Periksa perintah admin khusus
    if from_number in ADMIN_PHONES and user_message.startswith("/update "):
        new_info = user_message.replace("/update ", "")
        add_update(new_info)
        return f"✅ Update berhasil ditambahkan: {new_info}"
    
    # Coba knowledge base dulu
    knowledge_context = get_knowledge_context()
    low_msg = user_message.lower()
    
    # Jawab pertanyaan umum dari knowledge base
    common_questions = {
        "halo": "Halo! Ada yang bisa saya bantu seputar layanan DISNAKER Bartim?",
        "jam buka": "Jam pelayanan: Senin-Kamis 08.00-14.00 WIB | Jumat 08.00-11.00 WIB",
        "alamat": "Kantor DISNAKER Bartim: Jl. Tjilik Riwut KM 5, Tamiang Layang",
        "kartu kuning": "Syarat kartu kuning:\n1. Fotokopi KTP\n2. Pas foto 3x4\n3. Surat pengantar kelurahan",
        "pelatihan": "Program pelatihan gratis: Teknisi HP, Menjahit, Las, Tata Rias",
        "kontak": "Hubungi kami:\n📞 0538-1234567\n✉️ diskertrans.bartim@gmail.com"
    }
    
    for keyword, response in common_questions.items():
        if keyword in low_msg:
            return response
    
    # Jika tidak ada di knowledge base, gunakan Groq AI
    return query_groq(user_message)

def query_groq(user_message):
    """Mengirim permintaan ke Groq API"""
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "Anda adalah asisten virtual Dinas Tenaga Kerja Barito Timur. "
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
        "model": "mixtral-8x7b-32768",  # Model gratis terbaik
        "temperature": 0.3,
        "max_tokens": 256,
        "stream": False
    }
    
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=15
        )
        
        logger.info(f"Groq API Response: {response.status_code} - {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            return data['choices'][0]['message']['content']
        elif response.status_code == 429:
            return "Maaf, layanan AI sedang sibuk. Silakan coba lagi sebentar."
        else:
            return "Maaf, terjadi kesalahan teknis. Silakan hubungi 0538-1234567."
            
    except Exception as e:
        logger.error(f"Groq API Error: {str(e)}")
        return "Layanan informasi sedang gangguan. Silakan coba lagi nanti."

@app.route('/')
def home():
    knowledge = load_knowledge()
    return jsonify({
        "status": "online",
        "provider": "Groq AI",
        "last_updated": datetime.now().isoformat(),
        "knowledge_stats": {
            "updates_count": len(knowledge['update_terbaru'])
        }
    })

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        # Parse pesan masuk dari Twilio
        incoming_msg = request.values.get('Body', '').strip()
        from_number = request.values.get('From', '').replace('whatsapp:', '')
        
        logger.info(f"Pesan masuk dari {from_number}: {incoming_msg}")
        
        # Lewati pesan kosong
        if not incoming_msg:
            return '', 200
            
        # Dapatkan respon
        bot_response = generate_ai_response(incoming_msg, from_number)
        
        # Kirim balasan
        twilio_client.messages.create(
            body=bot_response,
            from_=TWILIO_PHONE,
            to=f"whatsapp:{from_number}"
        )
        
        return '', 200
    
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
