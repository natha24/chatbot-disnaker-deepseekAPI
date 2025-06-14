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

def is_quest_
