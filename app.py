from flask import Flask, request, jsonify
import requests
import os
import json
import logging
import re
from datetime import datetime
from twilio.rest import Client
from knowledge import get_knowledge_context, load_knowledge, add_update
import html  # Untuk escape karakter khusus

app = Flask(__name__)

# Konfigurasi
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE = "whatsapp:+14155238886"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ADMIN_PHONES = json.loads(os.getenv("ADMIN_PHONES", "[]"))
SANDBOX_CODE = os.getenv("SANDBOX_CODE", "default-code")
WEB_SEARCH_API_KEY = os.getenv("WEB_SEARCH_API_KEY")  # API key untuk layanan pencarian web

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info(f"Twilio configured: {bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN)}")
logger.info(f"GROQ API configured: {bool(GROQ_API_KEY)}")
logger.info(f"Admin phones: {ADMIN_PHONES}")

# Inisialisasi klien Twilio
try:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    logger.info("Twilio client initialized successfully")
except Exception as e:
    logger.error(f"Twilio init error: {str(e)}")
    twilio_client = None

# =================== ENDPOINT WEBHOOK ===================
@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_data = request.form
    from_number = incoming_data.get("From")
    user_message = incoming_data.get("Body")

    logger.info(f"Pesan masuk dari {from_number}: {user_message}")

    if not user_message:
        return jsonify({"status": "no message received"}), 400

    # Dapatkan respon AI dari fungsi utama
    ai_reply = generate_ai_response(user_message, from_number)

    # Kirim kembali ke pengguna via Twilio
    if twilio_client:
        try:
            twilio_client.messages.create(
                body=ai_reply,
                from_=TWILIO_PHONE,
                to=from_number
            )
            logger.info(f"Balasan dikirim ke {from_number}")
        except Exception as e:
            logger.error(f"Gagal mengirim balasan: {str(e)}")
            return jsonify({"status": "failed", "error": str(e)}), 500

    return jsonify({"status": "ok"}), 200

# =================== FUNGSI TAMBAHAN ===================
def is_question_requires_web_search(question):
    web_triggers = ['jadwal', 'terbaru', 'update', 'sekarang', 'terkini', 'dibuka', 'tutup', 'lokasi', 'alamat', 'tempat']
    return any(trigger in question.lower() for trigger in web_triggers)

def perform_web_search(query):
    if not WEB_SEARCH_API_KEY:
        return None
    try:
        params = {
            'q': f"site:disnakertransperin.bartimkab.go.id {query}",
            'api_key': WEB_SEARCH_API_KEY,
            'engine': 'google',
            'num': 1
        }
        response = requests.get('https://serpapi.com/search', params=params, timeout=10)
        results = response.json()
        if 'organic_results' in results and results['organic_results']:
            top_result = results['organic_results'][0]
            return {
                'title': top_result.get('title', ''),
                'snippet': top_result.get('snippet', ''),
                'link': top_result.get('link', '')
            }
    except Exception as e:
        logger.error(f"Web search error: {str(e)}")
    return None

def is_too_robotic(response):
    robotic_indicators = ["dengan demikian", "berdasarkan", "dapat disimpulkan", "adalah sebagai berikut", "pertama, kedua"]
    return any(indicator in response.lower() for indicator in robotic_indicators)

def rewrite_response_naturally(response, question):
    response = re.sub(r"(\w)(\.|,)(\w)", r"\1\2 \3", response)
    if not re.search(r"(pak|bu|bapak|ibu|mas|mbak)", response, re.IGNORECASE):
        if "?" in question:
            response = "Pak/Bu, " + response
    if any(trigger in response.lower() for trigger in ["terima kasih", "selamat", "berhasil", "siap", "bisa"]):
        response += " 😊"
    elif any(trigger in response.lower() for trigger in ["maaf", "tidak bisa", "belum tersedia"]):
        response += " 🙏"
    if len(response.split()) > 30:
        sentences = re.split(r'(?<=[.!?]) +', response)
        if sentences:
            response = sentences[0]
            if len(sentences) > 1:
                response += " " + sentences[1][0].lower() + sentences[1][1:]
    return response

def should_enable_creative_mode(question):
    creative_triggers = ['beda', 'perbedaan', 'bandingkan', 'rekomendasi', 'saran', 'ide', 'cerita', 'pengalaman', 'contoh']
    return any(trigger in question.lower() for trigger in creative_triggers)

def generate_ai_response(user_message, from_number):
    if from_number in ADMIN_PHONES and user_message.startswith("/update "):
        new_info = user_message.replace("/update ", "")
        add_update(new_info)
        return f"✅ Update berhasil: {new_info}"
    common_responses = {
        "halo": "Halo! Ada yang bisa saya bantu seputar DISNAKER Bartim? 😊",
        "jam buka": "Jam pelayanan: Senin-Kamis 08.00-14.00 WIB | Jumat 08.00-11.00 WIB",
        "alamat": "Kantor DISNAKER Bartim: Jl. Tjilik Riwut KM 5, Tamiang Layang",
        "kartu kuning": "Syarat kartu kuning:\n1. Fotokopi KTP\n2. Pas foto 3x4\n3. Surat pengantar kelurahan",
        "pelatihan": "Program pelatihan gratis: Teknisi HP, Menjahit, Las, Tata Rias"
    }
    user_message_lower = user_message.lower()
    for keyword, response in common_responses.items():
        if keyword in user_message_lower:
            return response
    if is_question_requires_web_search(user_message):
        web_result = perform_web_search(user_message)
        if web_result:
            return f"Menurut info terbaru di website kami:\n{web_result['title']}\n{web_result['snippet']}\nLink: {web_result['link']}\n\nInfo bisa berubah, silakan konfirmasi ke 0538-1234567 😊"
    ai_response = query_groq(user_message)
    if should_enable_creative_mode(user_message):
        creative_response = generate_creative_response(user_message)
        if creative_response:
            ai_response = creative_response
    if is_too_robotic(ai_response):
        ai_response = rewrite_response_naturally(ai_response, user_message)
    return ai_response

def query_groq(user_message):
    if not GROQ_API_KEY:
        return "Maaf, layanan AI sedang dalam pemeliharaan"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    system_prompt = (
        "Anda adalah customer service Dinas Tenaga Kerja, Transmigrasi, dan Perindustrian Barito Timur (DISNAKERTRANSPERIN Bartim). "
        "Gunakan bahasa yang ramah, santai, dan natural seperti sedang berbicara langsung. Sertakan emoji jika relevan. "
        "Batasi jawaban maksimal 5 kalimat. Jika tidak tahu jawabannya, beri saran alternatif yang realistis."
    )
    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "model": "llama3-70b-8192",
        "temperature": 0.7,
        "max_tokens": 350,
        "stream": False
    }
    try:
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            return data['choices'][0]['message']['content']
        else:
            logger.error(f"Groq API error: {response.status_code} - {response.text}")
            return "Maaf, belum ada jawaban yang relevan."
    except Exception as e:
        logger.error(f"Groq API exception: {str(e)}")
        return "Maaf, layanan AI sedang sibuk. Silakan coba lagi nanti."

def generate_creative_response(user_message):
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        creative_prompt = (
            "Anda adalah asisten kreatif DISNAKERTRANSPERIN Bartim. Jawablah dengan pendek, kreatif, dan informatif. "
            "Gunakan analogi atau contoh. Maksimal 4 kalimat. Jika tidak tahu, beri rujukan internet atau kontak manual."
        )
        payload = {
            "messages": [
                {"role": "system", "content": creative_prompt},
                {"role": "user", "content": user_message}
            ],
            "model": "mixtral-8x7b-32768",
            "temperature": 0.9,
            "max_tokens": 400,
            "stream": False
        }
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            return data['choices'][0]['message']['content']
    except Exception as e:
        logger.error(f"Creative mode error: {str(e)}")
    return None

# =================== JALANKAN APP ===================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"Starting server on port {port}")
    app.run(host='0.0.0.0', port=port)
