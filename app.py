import os
import json
import logging
import re
import random
import time
import uuid
import requests
from flask import Flask, request, jsonify
from datetime import datetime
from twilio.rest import Client
from queue import Queue
from threading import Thread

app = Flask(__name__)

# ===================== KONFIGURASI =====================
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE = "whatsapp:+14155238886"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ADMIN_PHONES = json.loads(os.getenv("ADMIN_PHONES", "[]"))
SANDBOX_CODE = os.getenv("SANDBOX_CODE", "default-code")
WEB_SEARCH_API_KEY = os.getenv("WEB_SEARCH_API_KEY")
MAPS_LOCATION = os.getenv("MAPS_LOCATION", "https://maps.app.goo.gl/XXXXX")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===================== INISIALISASI TWILIO =====================
try:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    logger.info("Twilio client initialized successfully")
except Exception as e:
    logger.error(f"Twilio init error: {str(e)}")
    twilio_client = None

# ===================== SISTEM ANTRIAN UNTUK PENANGANAN RATE LIMIT =====================
message_queue = Queue()
SEND_RETRY_DELAY = 60  # 60 detik antara percobaan pengiriman

def message_sender_worker():
    """Worker untuk mengirim pesan dengan penanganan rate limit"""
    while True:
        try:
            message_data = message_queue.get()
            from_number = message_data['to']
            message_body = message_data['body']
            attempt = message_data.get('attempt', 0)
            message_id = message_data.get('id', str(uuid.uuid4()))
            
            if attempt > 3:
                logger.error(f"Gagal mengirim pesan {message_id} setelah 3 percobaan")
                message_queue.task_done()
                continue
                
            try:
                twilio_client.messages.create(
                    body=message_body,
                    from_=TWILIO_PHONE,
                    to=f"whatsapp:{from_number}"
                )
                logger.info(f"Pesan {message_id} terkirim ke {from_number}")
            except Exception as e:
                if "429" in str(e):
                    logger.warning(f"Rate limit terdeteksi, mencoba lagi dalam {SEND_RETRY_DELAY} detik")
                    message_data['attempt'] = attempt + 1
                    message_queue.put(message_data)
                    time.sleep(SEND_RETRY_DELAY)
                else:
                    logger.error(f"Error mengirim pesan {message_id}: {str(e)}")
            
            message_queue.task_done()
        except Exception as e:
            logger.error(f"Worker error: {str(e)}")

# Mulai worker thread
sender_thread = Thread(target=message_sender_worker, daemon=True)
sender_thread.start()

# ===================== KONFIGURASI DOMAIN & FUNGSI UTILITAS =====================
DOMAIN_KEYWORDS = [
    'disnaker', 'tenaga kerja', 'transmigrasi', 'perindustrian',
    'kartu kuning', 'ak1', 'pelatihan', 'lowongan', 'industri',
    'kerja', 'pencari kerja', 'phk', 'pemecatan', 'pesangon', 
    'hubungan industrial', 'mediasi', 'sengketa', 'bpjs ketenagakerjaan',
    'cari kerja', 'bursa kerja', 'transmigran', 'pelayanan', 'syarat',
    'jam buka', 'alamat', 'lokasi', 'kantor', 'dinas', 'bartim', 'barito timur'
]

# Penyimpanan konteks percakapan sederhana
conversation_context = {}

def is_greeting(message):
    """Deteksi pesan sapaan atau pembuka percakapan"""
    greetings = [
        'halo', 'hai', 'hi', 'pagi', 'siang', 'sore', 'malam',
        'selamat pagi', 'selamat siang', 'selamat sore', 'selamat malam',
        'assalamualaikum', 'salam', 'hey', 'helo'
    ]
    return any(greeting in message.lower() for greeting in greetings)

def generate_greeting_response():
    """Buat respons sapaan yang ramah dan natural"""
    current_hour = datetime.utcnow().hour + 7  # WIB UTC+7
    time_of_day = "pagi" if 5 <= current_hour < 11 else \
                 "siang" if 11 <= current_hour < 15 else \
                 "sore" if 15 <= current_hour < 19 else "malam"
    
    greetings = [
        f"Halo! Selamat {time_of_day} 😊 Ada yang bisa saya bantu seputar DISNAKERTRANSPERIN Bartim?",
        f"Selamat {time_of_day}! 🙏 Saya siap membantu Anda dengan informasi seputar ketenagakerjaan dan perindustrian Bartim",
        f"Hai! Selamat {time_of_day} 😊 Ada yang bisa saya bantu hari ini?"
    ]
    
    return random.choice(greetings)

def is_gratitude(message):
    """Deteksi ucapan terima kasih"""
    gratitudes = [
        'terima kasih', 'thanks', 'makasih', 'tengkyu', 'thx',
        'sangat membantu', 'membantu sekali', 'terimakasih'
    ]
    return any(gratitude in message.lower() for gratitude in gratitudes)

def generate_gratitude_response():
    """Buat respons untuk ucapan terima kasih"""
    responses = [
        "Sama-sama! 😊 Senang bisa membantu. Jika ada pertanyaan lain, silakan bertanya ya!",
        "Terima kasih kembali! 🙏 Jangan ragu hubungi kami jika butuh bantuan lebih lanjut",
        "Dengan senang hati! 😊 Semoga informasinya bermanfaat untuk Anda"
    ]
    return random.choice(responses)

def is_conversational(message):
    """Deteksi pesan percakapan umum yang wajar"""
    conversational = [
        'baik', 'kabar', 'apa kabar', 'bagaimana', 'siapa', 'kenapa',
        'bisa bantu', 'tolong', 'permisi', 'mohon bantuan'
    ]
    return any(term in message.lower() for term in conversational)

def is_question_requires_web_search(question):
    """Deteksi apakah pertanyaan memerlukan pencarian web"""
    web_triggers = [
        'lokasi', 'alamat', 'tempat', 'peta', 'maps',
        'sharelock', 'bagikan lokasi', 'bagikan alamat',
        'hubungan industrial', 'pemecatan', 'phk', 'pesangon',
        'prosedur', 'tatacara', 'syarat', 'proses', 'ketentuan'
    ]
    return any(trigger in question.lower() for trigger in web_triggers)

def perform_web_search(query, official_only=True):
    """Lakukan pencarian web dengan prioritas situs resmi"""
    if not WEB_SEARCH_API_KEY:
        return None
        
    try:
        # Konfigurasi pencarian
        params = {
            'q': f"{query}",
            'api_key': WEB_SEARCH_API_KEY,
            'engine': 'google',
            'num': 3,
            'hl': 'id'
        }
        
        # Prioritisasi situs resmi
        if official_only:
            params['q'] += " site:disnakertransperin.bartimkab.go.id OR site:kemnaker.go.id"
        
        response = requests.get('https://serpapi.com/search', params=params, timeout=15)
        results = response.json()
        
        if 'organic_results' in results and results['organic_results']:
            # Filter hasil yang relevan
            relevant_results = [
                r for r in results['organic_results'] 
                if any(domain in r.get('link', '') for domain in ['disnakertransperin', 'kemnaker'])
            ]
            
            # Ambil hasil terbaik
            return relevant_results[0] if relevant_results else results['organic_results'][0]
            
    except Exception as e:
        logger.error(f"Web search error: {str(e)}")
        
    return None

def extract_location_info():
    """Info lokasi standar untuk respons cepat"""
    return (
        "Kantor DISNAKERTRANSPERIN Bartim:\n"
        "📍 *Lokasi*: Jl. Tjilik Riwut KM 5, Tamiang Layang\n"
        "🗓️ *Jam Pelayanan*: Senin-Kamis 08.00-14.00 WIB | Jumat 08.00-11.00 WIB\n"
        "📞 *Telepon*: 0538-1234567\n"
        f"🗺️ *Peta*: {MAPS_LOCATION}"
    )

def handle_industrial_relations(question):
    """Penanganan khusus masalah hubungan industrial"""
    # Cari informasi prosedur mediasi
    web_result = perform_web_search("prosedur mediasi hubungan industrial", official_only=True)
    
    response = (
        "Untuk masalah hubungan industrial seperti pemutusan hubungan kerja (PHK), "
        "DISNAKERTRANSPERIN Bartim menyediakan layanan mediasi. Berikut langkah-langkahnya:\n\n"
        "1. Datang ke kantor dengan membawa dokumen pendukung (surat peringatan, kontrak kerja, dll)\n"
        "2. Isi formulir pengaduan\n"
        "3. Tim mediasi akan memproses dalam 7 hari kerja\n"
        "4. Mediasi akan dilaksanakan dengan melibatkan kedua belah pihak\n\n"
    )
    
    if web_result:
        response += (
            f"Info lebih detail: {web_result.get('link', '')}\n\n"
        )
    
    response += (
        "Kami sarankan Anda segera datang ke kantor untuk konsultasi langsung. "
        f"{extract_location_info()}"
    )
    
    return response

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
            prefixes = ["Pak/Bu, ", "Bapak/Ibu, ", "Saudara, "]
            response = random.choice(prefixes) + response
    
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
    
    # Jika pesan sangat pendek, beri kelonggaran
    if len(question.split()) <= 3:
        return True
    
    return any(keyword in question_lower for keyword in DOMAIN_KEYWORDS)

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

def handle_out_of_domain(question, from_number):
    """Tangani pertanyaan di luar domain dengan lebih elegan"""
    # Cek apakah ini kelanjutan percakapan
    if from_number in conversation_context:
        last_topic = conversation_context[from_number].get('topic', '')
        if last_topic:
            return (
                f"Maaf, saya fokus pada pembahasan {last_topic}. "
                f"Untuk pertanyaan lain, silakan hubungi kami di 0538-1234567 🙏"
            )
    
    # Respons lebih ramah untuk pertanyaan umum
    conversational_responses = [
        "Maaf, saya khusus membantu informasi seputar Dinas Tenaga Kerja, Transmigrasi, dan Perindustrian Barito Timur. "
        "Ada yang bisa saya bantu terkait layanan kami? 😊",
        
        "Saya fokus pada informasi DISNAKERTRANSPERIN Bartim. "
        "Kalau ada pertanyaan tentang ketenagakerjaan, pelatihan, atau perindustrian, saya siap membantu! 🙏",
        
        "Untuk pertanyaan di luar lingkup DISNAKERTRANSPERIN, saya belum bisa bantu. "
        "Tapi kalau ada yang ingin ditanyakan seputar layanan kami, saya dengan senang hati membantu 😊"
    ]
    
    return random.choice(conversational_responses)

# ===================== FUNGSI UTAMA GENERASI RESPONS =====================
def generate_ai_response(user_message, from_number):
    """Mengirim permintaan ke Groq API dengan peningkatan baru"""
    user_message_lower = user_message.lower()
    
    # 1. Tangani sapaan dengan ramah
    if is_greeting(user_message_lower):
        return generate_greeting_response()
    
    # 2. Tangani ucapan terima kasih
    if is_gratitude(user_message_lower):
        return generate_gratitude_response()
    
    # 3. Periksa perintah admin khusus
    if from_number in ADMIN_PHONES and user_message.startswith("/update "):
        new_info = user_message.replace("/update ", "")
        return f"✅ Update berhasil: {new_info}"
    
    # 4. Tangani permintaan lokasi khusus
    if "lokasi" in user_message_lower or "alamat" in user_message_lower or "maps" in user_message_lower:
        return extract_location_info()
    
    # 5. Tangani permintaan share location
    if "sharelock" in user_message_lower or "bagikan lokasi" in user_message_lower:
        return (
            f"{extract_location_info()}\n\n"
            "Silakan klik link peta di atas untuk petunjuk arah."
        )
    
    # 6. Tangani masalah hubungan industrial
    industrial_keywords = ['phk', 'pemecatan', 'pesangon', 'hubungan industrial', 'sengketa kerja']
    if any(kw in user_message_lower for kw in industrial_keywords):
        return handle_industrial_relations(user_message)
    
    # 7. Cek relevansi domain - lebih fleksibel untuk percakapan umum
    if not is_in_domain(user_message) and not is_conversational(user_message_lower):
        response = handle_out_of_domain(user_message, from_number)
        track_conversation_context(from_number, user_message, response)
        return response
    
    # 8. Jawaban untuk pertanyaan umum dengan template lebih baik
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
    for keyword, response in common_responses.items():
        # Gunakan regex untuk pencocokan lebih tepat
        if re.search(r'\b' + re.escape(keyword) + r'\b', user_message_lower):
            track_conversation_context(from_number, user_message, response)
            return response
    
    # 9. Cek apakah perlu pencarian web untuk info terkini
    if is_question_requires_web_search(user_message):
        web_result = perform_web_search(user_message)
        if web_result:
            response = (
                f"🔍 Berdasarkan informasi terbaru:\n"
                f"*{web_result.get('title', 'Info terkait')}*\n"
                f"{web_result.get('snippet', '')}\n\n"
                f"📚 Sumber: {web_result.get('link', '')}\n\n"
                "Info dapat berubah, silakan konfirmasi ke 0538-1234567 untuk verifikasi."
            )
            track_conversation_context(from_number, user_message, response)
            return response
    
    # 10. Gunakan Groq AI dengan prompt yang ditingkatkan
    ai_response = query_groq(user_message)
    
    # 11. Aktifkan mode kreatif jika diperlukan
    if should_enable_creative_mode(user_message):
        creative_response = generate_creative_response(user_message)
        if creative_response:
            ai_response = creative_response
    
    # 12. Periksa dan perbaiki respon yang terlalu kaku
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
        "2. JANGAN PERNAH MEMBERIKAN INFORMASI DI LUAR DOMAIN INI\n"
        "3. JIKA PERTANYAAN DI LUAR TOPIK, KATAKAN: 'Maaf, saya hanya bisa bantu seputar DISNAKERTRANSPERIN Bartim'\n"
        "4. UNTUK PERTANYAAN UMUM, GUNAKAN RESPONS STANDAR YANG TELAH DITENTUKAN\n"
        "5. JANGAN MEMBUAT INFORMASI JIKA TIDAK TAHU\n"
        "6. GUNAKAN BAHASA INDONESIA YANG SANTUN DAN RAMAH\n"
        "7. MAKSIMAL 4 KALIMAT\n\n"
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

# ===================== ROUTE FLASK =====================
@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "service": "DISNAKER Bartim Chatbot",
        "version": "2.0",
        "features": [
            "Natural conversation handling",
            "Rate limit management",
            "Domain-focused responses",
            "Location sharing",
            "Industrial relations support"
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
        
        # Masukkan ke antrian pengiriman
        message_data = {
            'id': str(uuid.uuid4()),
            'to': from_number,
            'body': bot_response,
            'attempt': 0
        }
        message_queue.put(message_data)
        logger.info(f"Pesan dimasukkan ke antrian: {message_data['id']}")
        
        return '', 200
    
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"Starting DISNAKER Chatbot on port {port}")
    app.run(host='0.0.0.0', port=port)
