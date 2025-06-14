from flask import Flask, request, jsonify
import requests
import os
import json
from datetime import datetime
from twilio.rest import Client
from knowledge import get_knowledge_context, load_knowledge, add_update

app = Flask(__name__)

# Konfigurasi
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE = "whatsapp:+14155238886"  # Sandbox number
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
ADMIN_PHONES = json.loads(os.getenv("ADMIN_PHONES", "[]"))  # Nomor admin untuk perintah khusus

# Inisialisasi klien Twilio
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

def generate_ai_response(user_message, from_number):
    """Mengirim permintaan ke DeepSeek API dengan konteks knowledge base"""
    knowledge_context = get_knowledge_context()
    
    # Periksa perintah admin khusus
    if from_number in ADMIN_PHONES and user_message.startswith("/update "):
        new_info = user_message.replace("/update ", "")
        add_update(new_info)
        return f"✅ Update berhasil ditambahkan: {new_info}"
    
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": (
                    "Anda adalah asisten virtual Dinas Tenaga Kerja Barito Timur (DISNAKER Bartim). "
                    "Gunakan informasi resmi berikut untuk menjawab pertanyaan:\n\n"
                    f"{knowledge_context}\n\n"
                    "PETUNJUK:\n"
                    "1. Gunakan Bahasa Indonesia yang formal dan sopan\n"
                    "2. Fokus pada layanan ketenagakerjaan di Kabupaten Barito Timur\n"
                    "3. Jika pertanyaan di luar cakupan, sarankan untuk menghubungi kontak resmi\n"
                    "4. Jangan mengarang informasi yang tidak ada dalam knowledge base\n"
                    "5. Untuk pertanyaan umum, gunakan knowledge base sebagai referensi utama"
                )
            },
            {
                "role": "user",
                "content": user_message
            }
        ],
        "temperature": 0.3  # Kurangi kreativitas untuk akurasi lebih tinggi
    }
    
    try:
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=15
        )
        response_data = response.json()
        return response_data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Error DeepSeek API: {e}")
        return "Maaf, sedang ada gangguan teknis. Silakan coba lagi nanti."

@app.route('/')
def home():
    knowledge = load_knowledge()
    return jsonify({
        "status": "online",
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
        
        print(f"Pesan masuk dari {from_number}: {incoming_msg}")
        
        # Lewati pesan kosong
        if not incoming_msg:
            return '', 200
            
        # Dapatkan respon dari AI
        bot_response = generate_ai_response(incoming_msg, from_number)
        
        # Kirim balasan
        twilio_client.messages.create(
            body=bot_response,
            from_=TWILIO_PHONE,
            to=f"whatsapp:{from_number}"
        )
        
        return '', 200
    
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
