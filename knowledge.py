import json
import os
from datetime import datetime

# Konfigurasi file pengetahuan
KNOWLEDGE_FILE = "disnaker_knowledge.json"
DEFAULT_KNOWLEDGE = {
    "meta": {
        "last_updated": datetime.now().isoformat(),
        "version": "1.0",
        "maintainer": "Dinas Tenaga Kerja Barito Timur"
    },
    "info_dinas": {
        "nama_resmi": "Dinas Tenaga Kerja dan Transmigrasi Kabupaten Barito Timur",
        "alamat": "Jl. Tjilik Riwut KM 5, Tamiang Layang, Kalimantan Tengah",
        "telepon": "0538-1234567",
        "email": "diskertrans.bartim@gmail.com",
        "website": "https://disnakertrans.bartimkab.go.id",
        "jam_operasional": "Senin-Kamis: 08.00-14.00 WIB | Jumat: 08.00-11.00 WIB"
    },
    "layanan": {
        "kartu_kuning": {
            "nama": "Kartu Pencari Kerja (AK-1)",
            "deskripsi": "Kartu identitas pencari kerja yang diterbitkan oleh Dinas Tenaga Kerja",
            "syarat": [
                "Fotokopi KTP yang masih berlaku",
                "Pas foto ukuran 3x4 cm (latar belakang merah, 2 lembar)",
                "Surat pengantar dari Kelurahan/Desa",
                "Fotokopi ijazah terakhir yang dilegalisir"
            ],
            "prosedur": "1. Datang ke kantor DISNAKER Bartim\n2. Ambil nomor antrian di loket\n3. Isi formulir pendaftaran\n4. Serahkan persyaratan\n5. Tunggu proses verifikasi (1-2 hari kerja)",
            "biaya": "GRATIS"
        },
        "pelatihan_vokasi": {
            "nama": "Pelatihan Keterampilan Kerja",
            "deskripsi": "Program pelatihan gratis untuk meningkatkan kompetensi kerja warga Barito Timur",
            "jenis_pelatihan": [
                {"nama": "Teknisi Handphone", "durasi": "2 bulan"},
                {"nama": "Las Dasar", "durasi": "1 bulan"},
                {"nama": "Tata Rias Pengantin", "durasi": "1 month"},
                {"nama": "Menenun Tradisional", "durasi": "3 bulan"}
            ],
            "syarat_peserta": [
                "Warga Barito Timur",
                "Usia 18-45 tahun",
                "Fotokopi KTP"
            ],
            "pendaftaran": "1. Via WhatsApp DISNAKER\n2. Datang langsung ke kantor"
        }
    },
    "update_terbaru": [
        "Pendaftaran pelatihan teknisi handphone gelombang 5 dibuka hingga 30 Juni 2025",
        "Lowongan kerja di PT. Sawit Makmur: Operator produksi (10 orang)"
    ],
    "faq": [
        {
            "pertanyaan": "Bagaimana cara mengetahui lowongan kerja terbaru?",
            "jawaban": "Info lowongan kerja terbaru dapat diakses di website dinas"
        }
    ]
}

def load_knowledge():
    """Memuat knowledge base dari file JSON"""
    if not os.path.exists(KNOWLEDGE_FILE):
        # Buat file default jika belum ada
        save_knowledge(DEFAULT_KNOWLEDGE)
        return DEFAULT_KNOWLEDGE
    
    try:
        with open(KNOWLEDGE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading knowledge: {str(e)}")
        return DEFAULT_KNOWLEDGE

def save_knowledge(data):
    """Menyimpan knowledge base ke file JSON"""
    try:
        # Update metadata
        data['meta']['last_updated'] = datetime.now().isoformat()
        
        with open(KNOWLEDGE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving knowledge: {str(e)}")
        return False

def add_update(info_baru):
    """Menambahkan update baru ke knowledge base"""
    knowledge = load_knowledge()
    
    # Format update
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")
    formatted_update = f"{info_baru} [Ditambahkan: {timestamp}]"
    
    # Tambahkan ke bagian atas
    if 'update_terbaru' not in knowledge:
        knowledge['update_terbaru'] = []
    knowledge['update_terbaru'].insert(0, formatted_update)
    
    # Batasi hanya 10 update terbaru
    knowledge['update_terbaru'] = knowledge['update_terbaru'][:10]
    
    return save_knowledge(knowledge)

def get_knowledge_context():
    """Mengembalikan ringkasan knowledge base untuk prompt AI"""
    knowledge = load_knowledge()
    
    context = f"""
# INFORMASI RESMI DISNAKER BARITO TIMUR
## Informasi Umum
- Alamat: {knowledge['info_dinas']['alamat']}
- Telp: {knowledge['info_dinas']['telepon']} 
- Website: {knowledge['info_dinas']['website']}
- Jam Operasional: {knowledge['info_dinas']['jam_operasional']}

## Layanan Unggulan
### 1. {knowledge['layanan']['kartu_kuning']['nama']}
**Syarat:**
{format_list(knowledge['layanan']['kartu_kuning']['syarat'])}

### 2. {knowledge['layanan']['pelatihan_vokasi']['nama']}
**Jenis Pelatihan:**
{format_training(knowledge['layanan']['pelatihan_vokasi']['jenis_pelatihan'])}

## Update Terbaru
{format_list(knowledge['update_terbaru'])}
"""
    return context.strip()

def format_list(items):
    """Format list menjadi string dengan bullet points"""
    return "\n".join([f"- {item}" for item in items])

def format_training(items):
    """Format khusus untuk jenis pelatihan"""
    return "\n".join([f"- {item['nama']} ({item['durasi']})" for item in items])

# Inisialisasi: jika file belum ada, buat dengan data default
if not os.path.exists(KNOWLEDGE_FILE):
    save_knowledge(DEFAULT_KNOWLEDGE)
