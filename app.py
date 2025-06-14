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
WEB_SEARCH_API_KEY = os.getenv("WEB_SEARCH_API_KEY")

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

# Endpoint root (untuk Railway dan testing)
@app.route("/", methods=["GET"])
def home():
    return "DISNAKER Chatbot aktif ✅", 200

# Endpoint webhook untuk pesan masuk
@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_data = request.form
    from_number = incoming_data.get("From")
    user_message = incoming_data.get("Body")

    logger.info(f"Pesan masuk dari {from_number}: {user_message}")

    if not user_message:
        return jsonify({"status": "no message received"}), 400

    ai_reply = generate_ai_response(user_message, from_number)

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

# --- Fungsi pendukung lainnya tetap sama seperti sebelumnya ---

def is_question_requires_web_search(question):
    triggers = ['jadwal', 'terbaru', 'update', 'sekarang', 'terkini', 'dibuka', 'tutup', 'lokasi', 'alamat', 'tempat']
    return any(trigger in question.lower() for trigger in triggers)

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
            top = results['organic_results'][0]
            return {
                'title': top.get('title', ''),
                'snippet': top.get('snippet', ''),
                'link': top.get('link', '')
            }
    except Exception as e:
        logger.error(f"Web search error: {str(e)}")
    return None

def is_too_robotic(response):
    phrases = ["dengan demikian", "berdasarkan", "dapat disimpulkan", "adalah sebagai berikut", "pertama, kedua"]
    return any(p in response.lower() for p in phrases)

def rewrite_response_naturally(response, question):
    response = re.sub(r"(\w)(\.|,)(\w)", r"\1\2 \3", response)
    if not re.search(r"(pak|bu|bapak|ibu|mas|mbak)", response, re.IGNORECASE):
        if "?" in question:
            response = "Pak/Bu, " + response
    if any(k in response.lower() for k in ["terima kasih", "selamat", "berhasil", "siap", "bisa"]):
        response += " 😊"
    elif any(k in response.lower() for k in ["maaf", "tidak bisa", "belum tersedia"]):
        response += " 🙏"
    if len(response.split()) > 30:
        s = re.split(r'(?<=[.!?]) +', response)
        if s:
            response = s[0]
            if len(s) > 1:
                response += " " + s[1][0].lower() + s[1][1:]
    return response

def should_enable_creative_mode(question):
    return any(word in question.lower() for word in ['beda', 'perbedaan', 'bandingkan', 'rekomendasi', 'saran', 'ide', 'cerita', 'pengalaman', 'contoh'])

def generate_ai_response(user_message, from_number):
    if from_number in ADMIN_PHONES and user_message.startswith("/update "):
        new_info = user_message.replace("/update ", "")
        add_update(new_info)
        return f"✅ Update berhasil: {new_info}"
    
    general = {
        "halo": "Halo! Ada yang bisa saya bantu seputar DISNAKER Bartim? 😊",
        "jam buka": "Jam pelayanan: Senin-Kamis 08.00-14.00 WIB | Jumat 08.00-11.00 WIB",
        "alamat": "Kantor DISNAKER Bartim: Jl. Tjilik Riwut KM 5, Tamiang Layang",
        "kartu kuning": "Syarat kartu kuning:\n1. Fotokopi KTP\n2. Pas foto 3x4\n3. Surat pengantar kelurahan",
        "pelatihan": "Program pelatihan gratis: Teknisi HP, Menjahit, Las, Tata Rias"
    }

    text = user_message.lower()
    for k, v in general.items():
        if k in text:
            return v

    if is_question_requires_web_search(user_message):
        r = perform_web_search(user_message)
        if r:
            return f"Menurut info terbaru di website kami:\n{r['title']}\n{r['snippet']}\nLink: {r['link']}\n\nSilakan konfirmasi ke 0538-1234567 😊"

    ai_response = query_groq(user_message)
    if should_enable_creative_mode(user_message):
        cr = generate_creative_response(user_message)
        if cr:
            ai_response = cr
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
    prompt = (
        "Anda adalah asisten ramah DISNAKERTRANS Bartim. "
        "Jawablah dengan gaya informal, sopan, dan pakai emoji jika cocok. Maksimal 5 kalimat."
    )
    payload = {
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_message}
        ],
        "model": "llama3-70b-8192",
        "temperature": 0.7,
        "max_tokens": 350
    }
    try:
        res = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=15)
        if res.status_code == 200:
            return res.json()['choices'][0]['message']['content']
        logger.error(f"Groq error: {res.status_code} - {res.text}")
    except Exception as e:
        logger.error(f"Groq error: {str(e)}")
    return "Maaf, sistem sedang sibuk. Coba lagi nanti."

def generate_creative_response(user_message):
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        prompt = (
            "Anda adalah asisten kreatif DISNAKERTRANS Bartim. Jawab singkat, menarik, dan penuh ide. "
            "Gunakan contoh atau analogi jika bisa. Maksimal 4 kalimat."
        )
        payload = {
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_message}
            ],
            "model": "mixtral-8x7b-32768",
            "temperature": 0.9,
            "max_tokens": 400
        }
        res = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=15)
        if res.status_code == 200:
            return res.json()['choices'][0]['message']['content']
    except Exception as e:
        logger.error(f"Creative error: {str(e)}")
    return None

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"Starting server on port {port}")
    app.run(host='0.0.0.0', port=port)
