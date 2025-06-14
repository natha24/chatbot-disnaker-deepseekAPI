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

# Inisialisasi klien Twilio
try:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    logger.info("Twilio client initialized successfully")
except Exception as e:
    logger.error(f"Twilio init error: {str(e)}")
    twilio_client = None

# ========== FUNGSI BARU UNTUK PENINGKATAN ==========
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
        # Contoh implementasi dengan SerpAPI (bisa diganti dengan layanan lain)
        params = {
            'q': f"site:disnakertransperin.bartimkab.go.id {query}",
            'api_key': WEB_SEARCH_API_KEY,
            'engine': 'google',
            'num': 1  # Hanya ambil 1 hasil teratas
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
        "pertama, kedua"
    ]
    return any(indicator in response.lower() for indicator in robotic_indicators)

def rewrite_response_naturally(response, question):
    """Ubah respon kaku menjadi lebih natural"""
    # Heuristik sederhana untuk membuat respon lebih manusiawi
    response = re.sub(r"(\w)(\.|,)(\w)", r"\1\2 \3", response)  # Tambah spasi setelah titik/koma
    
    # Tambahkan sapaan jika belum ada
    if not re.search(r"(pak|bu|bapak|ibu|mas|mbak)", response, re.IGNORECASE):
        if "?" in question:  # Jika pertanyaan diajukan dengan sopan
            response = "Pak/Bu, " + response
    
    # Tambahkan emoji jika sesuai konteks
    positive_triggers = ["terima kasih", "selamat", "berhasil", "siap", "bisa"]
    negative_triggers = ["maaf", "tidak bisa", "belum tersedia"]
    
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
                response += " " + sentences[1][0].lower() + sentences[1][1:]
    
    return response

def should_enable_creative_mode(question):
    """Tentukan apakah perlu mengaktifkan mode kreatif"""
    creative_triggers = [
        'beda', 'perbedaan', 'bandingkan', 
        'rekomendasi', 'saran', 'ide',
        'cerita', 'pengalaman', 'contoh'
    ]
    return any(trigger in question.lower() for trigger in creative_triggers)

# ========== MODIFIKASI FUNGSI YANG SUDAH ADA ==========
def generate_ai_response(user_message, from_number):
    """Mengirim permintaan ke Groq API dengan peningkatan baru"""
    # Periksa perintah admin khusus
    if from_number in ADMIN_PHONES and user_message.startswith("/update "):
        new_info = user_message.replace("/update ", "")
        add_update(new_info)
        return f"✅ Update berhasil: {new_info}"
    
    # Jawaban untuk pertanyaan umum
    common_responses = {
        "halo": "Halo! Ada yang bisa saya bantu seputar DISNAKER Bartim? 😊",
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
    
    # 1. Cek apakah perlu pencarian web untuk info terkini
    if is_question_requires_web_search(user_message):
        web_result = perform_web_search(user_message)
        if web_result:
            return (
                f"Menurut info terbaru di website kami:\n"
                f"{web_result['title']}\n"
                f"{web_result['snippet']}\n"
                f"Link: {web_result['link']}\n\n"
                f"Info bisa berubah, silakan konfirmasi ke 0538-1234567 😊"
            )
    
    # 2. Gunakan Groq AI dengan prompt yang ditingkatkan
    ai_response = query_groq(user_message)
    
    # 3. Aktifkan mode kreatif jika diperlukan
    if should_enable_creative_mode(user_message):
        creative_response = generate_creative_response(user_message)
        if creative_response:
            ai_response = creative_response
    
    # 4. Periksa dan perbaiki respon yang terlalu kaku
    if is_too_robotic(ai_response):
        ai_response = rewrite_response_naturally(ai_response, user_message)
    
    return ai_response

def query_groq(user_message):
    """Mengirim permintaan ke Groq API dengan prompt yang lebih natural"""
    if not GROQ_API_KEY:
        return "Maaf, layanan AI sedang dalam pemeliharaan"
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # PROMPT YANG DIUBAH UNTUK RESPON LEBIH NATURAL
    system_prompt = (
        "Anda adalah customer service Dinas Tenaga Kerja, Transmigrasi, dan Perindustrian "
        "Barito Timur (DISNAKERTRANSPERIN Bartim). Gunakan bahasa yang ramah, santai, dan natural "
        "seperti sedang berbicara langsung. Sertakan emoji jika relevan. Batasi jawaban maksimal 5 kalimat. "
        "Fokus pada topik ketenagakerjaan, transmigrasi, dan perindustrian. "
        "Jika tidak tahu jawaban pastinya, jangan memaksakan jawaban, tetapi berikan alternatif: "
        "'Saya belum punya info pastinya, tapi bisa coba cek di [sumber] atau hubungi [nomor kontak]'. "
        "Contoh jawaban natural:\n"
        "User: 'Kapan pelatihan las dibuka?'\n"
        "Asisten: 'Pelatihan las biasanya dibuka setiap bulan awal, Pak/Bu. 😊 Tapi untuk jadwal pasti bulan ini, "
        "saya sarankan cek di website kami atau telepon ke 0538-1234567 ya.'"
    )
    
    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "model": "llama3-70b-8192",
        "temperature": 0.7,  # Lebih tinggi untuk kreativitas
        "max_tokens": 350,    # Lebih panjang untuk respon natural
        "stream": False
    }
    
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=15  # Timeout lebih panjang
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
            "Untuk pertanyaan berikut, berikan jawaban yang: "
            "1. Menawarkan perspektif unik tapi tetap relevan "
            "2. Gunakan analogi atau contoh konkret "
            "3. Sertakan pertanyaan lanjutan untuk merangsang pemikiran "
            "4. Tetap akurat secara informasi "
            "5. Maksimal 4 kalimat"
            "6. untuk pertanyaan yang tidak ada di base knowladge, tetapi berkaitan dengan disnakertransperin bisa di cari referensinya dari internet"
        )
        
        payload = {
            "messages": [
                {"role": "system", "content": creative_prompt},
                {"role": "user", "content": user_message}
            ],
            "model": "mixtral-8x7b-32768",  # Model yang lebih kreatif
            "temperature": 0.9,
            "max_tokens": 400,
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

# Fungsi lainnya tetap sama...
# (answer_from_knowledge, home, test_endpoint, webhook)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))  # Default ke 8080 jika tidak ada env var
    app.run(host='0.0.0.0', port=port)
