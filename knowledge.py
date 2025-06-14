import json
import os

KNOWLEDGE_FILE = "knowledge.json"

# Di fungsi cari_jawaban()
def cari_jawaban(pertanyaan):
    pertanyaan = pertanyaan.lower()
    
    # Pertanyaan sangat umum
    if any(k in pertanyaan for k in ["halo", "hai", "pagi", "siang"]):
        return "Halo! Ada yang bisa saya bantu seputar layanan DISNAKER Bartim?"
    
    if "jam buka" in pertanyaan:
        return "Jam pelayanan: Senin-Kamis 08.00-14.00 WIB | Jumat 08.00-11.00 WIB"

def load_knowledge():
    """Memuat knowledge base dari file JSON"""
    if not os.path.exists(KNOWLEDGE_FILE):
        # Inisialisasi knowledge base default
        default_knowledge = {
            "info_dinas": {
                "jam_operasional": "Senin-Kamis: 08.00-14.00 WIB | Jumat: 08.00-11.00 WIB",
                "alamat": "Jl. Tjilik Riwut KM 5, Tamiang Layang, Kalimantan Tengah",
                "kontak": "0538-1234567 | diskertrans.bartim@gmail.com"
            },
            "layanan": {
                "kartu_kuning": {
                    "syarat": [
                        "Fotokopi KTP",
                        "Pas foto 3x4 (latar merah)",
                        "Surat pengantar dari kelurahan",
                        "Ijazah terakhir yang dilegalisir"
                    ],
                    "prosedur": "Datang ke kantor DISNAKER Bartim dengan membawa persyaratan lengkap"
                },
                "pelatihan": {
                    "jenis": ["Teknisi HP", "Menenun", "Las Dasar", "Tata Rias"],
                    "pendaftaran": "Via WhatsApp ini atau langsung ke kantor"
                }
            },
            "update_terbaru": []
        }
        save_knowledge(default_knowledge)
    
    with open(KNOWLEDGE_FILE, 'r') as f:
        return json.load(f)

def save_knowledge(data):
    """Menyimpan knowledge base ke file JSON"""
    with open(KNOWLEDGE_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def get_knowledge_context():
    """Mengembalikan konteks knowledge base untuk prompt AI"""
    knowledge = load_knowledge()
    context = """
# INFORMASI RESMI DISNAKER BARITO TIMUR
## Informasi Umum
- Jam Operasional: {jam_operasional}
- Alamat: {alamat}
- Kontak: {kontak}

## Layanan Unggulan
### Kartu Kuning (AK-1)
**Syarat:**
{list_syarat_kartu_kuning}

**Prosedur:**
{kartu_kuning_prosedur}

### Program Pelatihan
**Jenis Pelatihan:**
{list_jenis_pelatihan}

**Pendaftaran:**
{pelatihan_pendaftaran}

## Update Terbaru
{list_update_terbaru}
""".format(
        jam_operasional=knowledge['info_dinas']['jam_operasional'],
        alamat=knowledge['info_dinas']['alamat'],
        kontak=knowledge['info_dinas']['kontak'],
        list_syarat_kartu_kuning="\n".join([f"- {s}" for s in knowledge['layanan']['kartu_kuning']['syarat']]),
        kartu_kuning_prosedur=knowledge['layanan']['kartu_kuning']['prosedur'],
        list_jenis_pelatihan="\n".join([f"- {j}" for j in knowledge['layanan']['pelatihan']['jenis']]),
        pelatihan_pendaftaran=knowledge['layanan']['pelatihan']['pendaftaran'],
        list_update_terbaru="\n".join([f"- {u}" for u in knowledge['update_terbaru']]) if knowledge['update_terbaru'] else "Tidak ada update terbaru"
    )
    return context

def add_update(info_baru):
    """Menambahkan update baru ke knowledge base"""
    knowledge = load_knowledge()
    knowledge['update_terbaru'].insert(0, f"{info_baru} [Ditambahkan pada: {datetime.now().strftime('%d/%m/%Y')}]")
    
    # Batasi hanya 5 update terbaru
    knowledge['update_terbaru'] = knowledge['update_terbaru'][:5]
    save_knowledge(knowledge)


# Tambahkan konfigurasi
SANDBOX_NUMBER = "whatsapp:+14155238886"
ADMIN_NUMBER = "whatsapp:+6285245407566"

# Di dalam fungsi webhook
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        incoming_msg = request.values.get('Body', '').strip()
        from_number = request.values.get('From', '')
        
        # Identifikasi apakah pesan dari admin
        is_from_admin = from_number == ADMIN_NUMBER
        
        logger.info(f"Pesan dari {'ADMIN' if is_from_admin else 'USER'}: {incoming_msg}")
        
        # Proses pesan dari admin sebagai perintah khusus
        if is_from_admin:
            if incoming_msg.startswith("/"):
                # Eksekusi perintah admin
                bot_response = handle_admin_command(incoming_msg)
            else:
                # Tangani sebagai pesan biasa
                bot_response = generate_ai_response(incoming_msg, from_number)
        else:
            # Tangani pesan dari pengguna biasa
            bot_response = generate_ai_response(incoming_msg, from_number)
        
        # Kirim balasan
        twilio_client.messages.create(
            body=bot_response,
            from_=SANDBOX_NUMBER,
            to=from_number
        )
        
        return '', 200
    
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

def handle_admin_command(command):
    """Tangani perintah khusus admin"""
    if command.startswith("/update "):
        new_info = command.replace("/update ", "")
        add_update(new_info)
        return f"✅ Update berhasil: {new_info}"
    
    elif command == "/stats":
        return "Status: Online | Pengguna: 25"
    
    else:
        return "Perintah admin tidak dikenali"
