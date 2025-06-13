from flask import Flask, request, jsonify
import requests
import os
from knowledge import cari_jawaban

app = Flask(__name__)

# Konfigurasi dari environment variables
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WEBHOOK_TOKEN = os.getenv("WEBHOOK_TOKEN", "bartim123")

def query_deepseek(prompt):
    """Mengirim permintaan ke API DeepSeek"""
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
                    "Anda adalah asisten virtual Dinas Tenaga Kerja Barito Timur. "
                    "Jawablah pertanyaan dengan sopan dalam Bahasa Indonesia. "
                    "Fokus pada layanan ketenagakerjaan. Jika tidak tahu jawabannya, "
                    "sarankan untuk menghubungi kontak resmi: Telp: 0538-1234567, Email: diskertrans.bartim@gmail.com"
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    }
    
    try:
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=15
        )
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Error DeepSeek API: {e}")
        return "Maaf, sedang ada gangguan teknis. Silakan coba lagi nanti atau hubungi kami langsung."

@app.route('/')
def home():
    return "Chatbot Dinas Tenaga Kerja Barito Timur siap melayani!"

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        return verify_webhook(request)
    
    try:
        data = request.json
        message = data['entry'][0]['changes'][0]['value']['messages'][0]
        user_msg = message['text']['body']
        phone_number = message['from']
        
        print(f"Pesan dari {phone_number}: {user_msg}")
        
        # Cari jawaban di basis pengetahuan
        response = cari_jawaban(user_msg)
        
        # Jika tidak ditemukan, gunakan DeepSeek
        if not response:
            print("Menggunakan DeepSeek untuk pertanyaan:", user_msg)
            response = query_deepseek(
                f"Pertanyaan tentang Dinas Tenaga Kerja Barito Timur: {user_msg}"
            )
        
        # Kirim balasan
        send_whatsapp_message(phone_number, response)
        return jsonify({"status": "success"}), 200
    
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

def verify_webhook(request):
    """Verifikasi webhook untuk WhatsApp"""
    hub_mode = request.args.get('hub.mode')
    hub_token = request.args.get('hub.verify_token')
    hub_challenge = request.args.get('hub.challenge')
    
    if hub_mode == 'subscribe' and hub_token == WEBHOOK_TOKEN:
        return hub_challenge, 200
    return "Verification failed", 403

def send_whatsapp_message(phone_number, message):
    """Mengirim pesan balasan melalui WhatsApp API"""
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "text": {"body": message}
    }
    
    try:
        response = requests.post(
            "https://graph.facebook.com/v17.0/me/messages",
            headers=headers,
            json=payload
        )
        print("Status pengiriman:", response.status_code)
    except Exception as e:
        print(f"Error mengirim pesan: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
