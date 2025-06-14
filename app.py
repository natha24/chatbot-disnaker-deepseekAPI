from flask import Flask, request, jsonify
import requests
import os
import json
import logging
from twilio.rest import Client
from knowledge import get_knowledge_context, add_update

app = Flask(__name__)

# Konfigurasi dari environment variable
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE = "whatsapp:+14155238886"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ADMIN_PHONES = json.loads(os.getenv("ADMIN_PHONES", "[]"))

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inisialisasi Twilio
try:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
except Exception as e:
    logger.error(f"Twilio init error: {str(e)}")
    twilio_client = None

@app.route("/", methods=["GET"])
def home():
    return "DISNAKER Chatbot aktif ✅", 200

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
        except Exception as e:
            logger.error(f"Gagal kirim balasan: {str(e)}")
            return jsonify({"status": "failed", "error": str(e)}), 500

    return jsonify({"status": "ok"}), 200

def is_question_off_topic(message):
    topic_keywords = [
        "ak1", "kartu kuning", "pelatihan", "disnaker", "industri", "transmigrasi",
        "lokasi", "jam buka", "lowongan", "kerja", "magang", "dinas"
    ]
    return not any(word in message.lower() for word in topic_keywords)

def generate_ai_response(user_message, from_number):
    if from_number in ADMIN_PHONES and user_message.startswith("/update "):
        new_info = user_message.replace("/update ", "")
        add_update(new_info)
        return f"✅ Update berhasil: {new_info}"

    if is_question_off_topic(user_message):
        return "Maaf, saya hanya bisa membantu seputar layanan DISNAKERTRANS Bartim. Coba tanyakan hal seperti AK1, pelatihan, atau lowongan kerja ya! 🙏"

    ai_response = query_groq(user_message)

    if not ai_response or len(ai_response.strip()) < 5:
        return get_knowledge_context(user_message) or "Maaf, saya belum tahu jawaban pastinya. Silakan hubungi langsung ke DISNAKERTRANS Bartim ya. 🙏"

    return ai_response

def query_groq(user_message):
    if not GROQ_API_KEY:
        return None

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    system_prompt = (
        "Anda adalah asisten resmi DISNAKERTRANS Bartim. Jawablah pertanyaan terkait layanan seperti AK1, pelatihan kerja, transmigrasi, perindustrian, lowongan kerja. "
        "Jika pertanyaan di luar itu, arahkan untuk bertanya hal relevan. Gunakan bahasa ramah dan ringkas. Sertakan emoji bila cocok."
    )

    payload = {
        "model": "llama3-70b-8192",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.7,
        "max_tokens": 350
    }

    try:
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
    except Exception as e:
        logger.error(f"Groq error: {str(e)}")
    return None

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
