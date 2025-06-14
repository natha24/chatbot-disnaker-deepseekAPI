from flask import Flask, request, jsonify
import requests
import os
import json
import logging
import re
from datetime import datetime
from twilio.rest import Client
import html

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

# Inisialisasi klien Twilio
try:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    logger.info("Twilio client initialized successfully")
except Exception as e:
    logger.error(f"Twilio init error: {str(e)}")
    twilio_client = None

# ========== KONFIGURASI DOMAIN ==========
DOMAIN_KEYWORDS = [
    'disnaker', 'tenaga kerja', 'transmigrasi', 'perindustrian',
    'kartu kuning', 'ak1', 'pelatihan', 'lowongan', 'industri',
    'kerja', 'pencari kerja', 'phk', 'pesangon', 'bpjs ketenagakerjaan',
    'cari kerja', 'bursa kerja', 'transmigran', 'pelayanan', 'syarat',
    'jam buka', 'alamat', 'lokasi', 'kantor', 'dinas', 'bartim', 'barito timur'
]

# Penyimpanan konteks percakapan sederhana
conversation_context = {}

# ========== FUNGSI UTILITAS ==========
def is_question_requires_web_search(question):
    """Deteksi apakah pertanyaan memerlukan pencarian web"""
    web_triggers = [
        'jadwal', 'terbaru', 'update', 'sekarang', 'terkini', 
        'dibuka', 'tutup', 'lokasi', 'alamat', 'tempat'
    ]
    return any(trigger in question.lower() for trigger in web_triggers)

def perform_web_search(query):
    """Lakukan pencarian web terbatas untuk info terkini"""
    if not WEB_SEARCH_API_KEY:
        return None
        
    try:
        # Implementasi dengan SerpAPI
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
    """Deteksi apakah respon terlalu kaku/robotik"""
    robotic_indicators = [
        "dengan demikian",
        "berdasarkan",
        "dapat disimpulkan",
        "adalah sebagai berikut",
        "pertama, kedua",
        "syarat"
    ]
    return any(indicator in response.lower() for indicator in robotic_indicators)

def rewrite_response_naturally(response, question):
    """Ubah respon kaku menjadi lebih natural"""
    # Tambahkan sapaan jika belum ada
    if not re.search(r"(pak|bu|bapak|ibu|mas|mbak)", response, re.IGNORECASE):
        if "?" in question:
            response = "Pak/Bu, " + response
    
    # Tambahkan emoji jika sesuai konteks
    positive_triggers = ["terima kasih", "selamat", "berhasil", "siap", "bisa", "informasi", "silakan"]
    negative_triggers = ["maaf", "tidak bisa", "belum tersedia", "tidak tahu"]
    
    if any(trigger in response.lower() for trigger in positive_triggers):
        response += " 😊"
    elif any(trigger in response.lower() for trigger in negative_triggers):
        response += " 🙏"
    
    # Singkatkan kalimat panjang
    if len(response.split()) > 30:
        sentences = re.split(r'(?<=[.!?]) +', response)
        if sentences:
            response = sentences[0]
            if len(sentences) > 1:
                response += " " + sentences[1]
    
    return response

def should_enable_creative_mode(question):
    """Tentukan apakah perlu mengaktifkan mode kreatif"""
    creative_triggers = [
        'beda', 'perbedaan', 'bandingkan', 
        'rekomendasi', 'saran', 'ide',
        'cerita', 'pengalaman', 'contoh'
    ]
    return any(trigger in question.lower() for trigger in creative_triggers)

def is_in_domain(question):
    """Cek apakah pertanyaan relevan dengan domain DISNAKERTRANSPERIN"""
    question_lower = question.lower()
    return any(keyword in question_lower for keyword in DOMAIN_KEYWORDS)

def handle_out_of_domain(question, from_number):
    """Tangani pertanyaan di luar domain dengan sopan"""
    # Cek apakah ini kelanjutan percakapan
    if from_number in conversation_context:
        last_topic = conversation_context[from_number].get('topic', '')
        if last_topic:
            return (
                f"Maaf, saya fokus pada pembahasan {last_topic}. "
                f"Untuk pertanyaan lain, silakan hubungi kami di 0538-1234567 🙏"
            )
    
    return (
        "Maaf, saya hanya bisa membantu pertanyaan seputar "
        "Dinas Tenaga Kerja, Transmigrasi, dan Perindustrian Barito Timur (DISNAKERTRANSPERIN). "
        "Ada yang bisa saya bantu terkait layanan kami? 😊"
    )

def track_conversation_context(from_number, question, response):
    """Simpan konteks percakapan terakhir"""
    if from_number not in conversation_context:
        conversation_context[from_number] = {}
    
    # Simpan topik terakhir
    conversation_context[from_number]['last_question'] = question
    conversation_context[from_number]['last_response'] = response
    
    # Ekstrak topik utama
    main_topic = "DISNAKERTRANSPERIN Bartim"
    for keyword in DOMAIN_KEYWORDS:
        if keyword in question.lower():
            main_topic = keyword
            break
    
    conversation_context[from_number]['topic'] = main_topic

# ========== FUNGSI UTAMA GENERASI RESPONS ==========
def generate_ai_response(user_message, from_number):
    """Mengirim permintaan ke Groq API dengan peningkatan baru"""
    # Periksa perintah admin khusus
    if from_number in ADMIN_PHONES and user_message.startswith("/update "):
        new_info = user_message.replace("/update ", "")
        # Fungsi add_update diasumsikan sudah diimplementasikan
        return f"✅ Update berhasil: {new_info}"
    
    # 1. Cek relevansi domain
    if not is_in_domain(user_message):
        response = handle_out_of_domain(user_message, from_number)
        track_conversation_context(from_number, user_message, response)
        return response
    
    # 2. Jawaban untuk pertanyaan umum dengan template lebih baik
    common_responses = {
        "halo": "Halo! Ada yang bisa saya bantu seputar DISNAKER Bartim? 😊",
        "jam buka": "Jam pelayanan: Senin-Kamis 08.00-14.00 WIB | Jumat 08.00-11.00 WIB",
        "alamat": "Kantor DISNAKER Bartim: Jl. Tjilik Riwut KM 5, Tamiang Layang",
        "kartu kuning": (
            "Syarat pembuatan Kartu Kuning (AK1):\n"
            "1. Fotokopi KTP\n"
            "2. Pas foto 3x4 (2 lembar)\n"
            "3. Surat pengantar dari kelurahan\n"
            "4. Mengisi formulir pendaftaran\n\n"
            "Kartu Kuning digunakan untuk pencari kerja pertama kali 😊"
        ),
        "ak1": (
            "Kartu AK1 adalah bukti pencatatan bagi pekerja yang pernah bekerja. "
            "Berbeda dengan Kartu Kuning yang untuk pencari kerja pertama kali.\n\n"
            "Syarat perpanjangan AK1:\n"
            "1. Fotokopi AK1 lama\n"
            "2. Fotokopi KTP\n"
            "3. Pas foto 4x6 (2 lembar)\n"
            "4. Surat pengantar dari perusahaan terakhir"
        ),
        "perbedaan ak1 dan kartu kuning": (
            "Perbedaan AK1 dan Kartu Kuning:\n"
            "1. **Kartu Kuning (AK/I)**: Untuk pencari kerja pertama kali (belum pernah bekerja)\n"
            "2. **AK1**: Untuk pekerja yang pernah bekerja (memiliki pengalaman kerja)\n\n"
            "Keduanya adalah dokumen penting dalam dunia ketenagakerjaan, "
            "tapi digunakan pada fase berbeda dalam karir seseorang 😊"
        ),
        "pelatihan": (
            "Program pelatihan gratis DISNAKER Bartim:\n"
            "- Teknisi HP\n"
            "- Menjahit\n"
            "- Las\n"
            "- Tata Rias\n"
            "- Komputer Dasar\n\n"
            "Pendaftaran: Setiap bulan pertama di Kantor DISNAKER atau online melalui disnakertransperin.bartimkab.go.id"
        )
    }
    
    # Cek pertanyaan umum dengan pencocokan lebih akurat
    user_message_lower = user_message.lower()
    for keyword, response in common_responses.items():
        # Gunakan regex untuk pencocokan lebih tepat
        if re.search(r'\b' + re.escape(keyword) + r'\b', user_message_lower):
            track_conversation_context(from_number, user_message, response)
            return response
    
    # 3. Cek apakah perlu pencarian web untuk info terkini
    if is_question_requires_web_search(user_message):
        web_result = perform_web_search(user_message)
        if web_result:
            response = (
                f"Menurut info terbaru di website kami:\n"
                f"{web_result['title']}\n"
                f"{web_result['snippet']}\n"
                f"Link: {web_result['link']}\n\n"
                f"Info bisa berubah, silakan konfirmasi ke 0538-1234567 😊"
            )
            track_conversation_context(from_number, user_message, response)
            return response
    
    # 4. Gunakan Groq AI dengan prompt yang ditingkatkan
    ai_response = query_groq(user_message)
    
    # 5. Aktifkan mode kreatif jika diperlukan
    if should_enable_creative_mode(user_message):
        creative_response = generate_creative_response(user_message)
        if creative_response:
            ai_response = creative_response
    
    # 6. Periksa dan perbaiki respon yang terlalu kaku
    if is_too_robotic(ai_response):
        ai_response = rewrite_response_naturally(ai_response, user_message)
    
    track_conversation_context(from_number, user_message, ai_response)
    return ai_response

def query_groq(user_message):
    """Mengirim permintaan ke Groq API dengan prompt yang lebih ketat"""
    if not GROQ_API_KEY:
        return "Maaf, layanan AI sedang dalam pemeliharaan"
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # PROMPT YANG DIUBAH DENGAN GUARDRAILS KETAT
    system_prompt = (
        "ANDA ADALAH CUSTOMER SERVICE RESMI DISNAKERTRANSPERIN BARTIM. \n"
        "**ATURAN KETAT**:\n"
        "1. HANYA JAWAB PERTANYAAN TERKAIT TENAGA KERJA, TRANSMIGRASI, DAN PERINDUSTRIAN\n"
        "2. BILA INGIN MEMBERI JAWABAN DI LUAR DOMAIN INI, BOLEH TAPI HARUS RELEVAN DENGAN URUSAN DISNAKERTRANSPERIN\n"
        "3. JIKA PERTANYAAN DI LUAR TOPIK, KATAKAN: 'Maaf, saya hanya bisa bantu seputar DISNAKERTRANSPERIN Bartim'\n"
        "4. UNTUK PERTANYAAN UMUM, GUNAKAN RESPONS STANDAR YANG TELAH DITENTUKAN\n"
        "5. BILA TIDAK TAHU CARI REFERENSI DARI WEB TETAPI HARUS TETAP RELEVAN DENGAN DISNAKERTRANSPERIN\n"
        "6. GUNAKAN BAHASA INDONESIA YANG SANTUN DAN RAMAH\n"
        "7. MAKSIMAL 4 KALIMAT\n\n"
        "8. SELALU PERTIMBANGKAN RELEVANSI DENGAN URUSAN DISNAKERTRANSPERIN, BILA TIDAK RELEVAN BERI JAWABAN YANG SOPAN AGAR CUSTOMER tetap di seputar topik dan layanan DISNAKERTRANSPERIN\n"
        "**CONTOH RESPONS YANG BENAR**:\n"
        "User: 'Apa beda AK1 dan kartu kuning?'\n"
        "Asisten: 'Kartu Kuning untuk pencari kerja pertama kali, sedangkan AK1 untuk yang pernah bekerja. Detail lengkap ada di website kami: disnakertransperin.bartimkab.go.id 😊'\n\n"
        "User: 'Bisa beli roti?'\n"
        "Asisten: 'Maaf, saya hanya membantu info seputar DISNAKERTRANSPERIN Bartim. Ada yang bisa saya bantu terkait layanan kami?'"
    )
    
    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "model": "llama3-70b-8192",
        "temperature": 0.5,  # Keseimbangan antara kreativitas dan akurasi
        "max_tokens": 300,
        "stream": False
    }
    
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            return data['choices'][0]['message']['content']
        else:
            logger.error(f"Groq API error: {response.status_code} - {response.text}")
            return answer_from_knowledge(user_message)
            
    except Exception as e:
        logger.error(f"Groq API exception: {str(e)}")
        return "Maaf, layanan AI sedang sibuk. Silakan coba lagi nanti."

def generate_creative_response(user_message):
    """Buat respon kreatif untuk pertanyaan yang membutuhkan pemikiran lateral"""
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        creative_prompt = (
            "Anda adalah asisten kreatif DISNAKERTRANSPERIN Bartim. "
            "Untuk pertanyaan berikut, berikan jawaban yang: \n"
            "1. Menawarkan perspektif unik tapi tetap relevan \n"
            "2. Gunakan analogi atau contoh konkret \n"
            "3. Tetap akurat secara informasi \n"
            "4. Maksimal 4 kalimat"
        )
        
        payload = {
            "messages": [
                {"role": "system", "content": creative_prompt},
                {"role": "user", "content": user_message}
            ],
            "model": "mixtral-8x7b-32768",
            "temperature": 0.8,
            "max_tokens": 350,
            "stream": False
        }
        
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            return data['choices'][0]['message']['content']
            
    except Exception as e:
        logger.error(f"Creative mode error: {str(e)}")
        
    return None

def answer_from_knowledge(user_message):
    """Fallback ke knowledge base jika Groq error"""
    low_msg = user_message.lower()
    
    if "lowongan" in low_msg or "pekerjaan" in low_msg:
        return "Info lowongan terbaru: disnakertrans.bartimkab.go.id/lowongan"
    
    if "layanan" in low_msg or "servis" in low_msg:
        return (
            "Layanan kami:\n"
            "1. Kartu Kuning\n"
            "2. Pelatihan Kerja\n"
            "3. Bantuan Sosial\n"
            "4. Mediasi Perburuhan"
        )
        
    return "Maaf, saya belum bisa menjawab pertanyaan tersebut. Silakan hubungi 0538-1234567 untuk bantuan lebih lanjut."

# ========== ROUTE FLASK ==========
@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "service": "DISNAKER Bartim Chatbot",
        "version": "1.2",
        "features": [
            "Domain-focused responses",
            "Natural language processing",
            "Context-aware conversations",
            "Web search integration"
        ]
    })

@app.route('/test')
def test_endpoint():
    return "Test endpoint working! Chatbot is operational.", 200

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
                logger.info("Webhook verified successfully")
                return hub_challenge, 200
            logger.warning("Webhook verification failed")
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
        logger.error(f"Webhook error: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"Starting DISNAKER Chatbot on port {port}")
    app.run(host='0.0.0.0', port=port)
