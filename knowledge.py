# Basis pengetahuan khusus Dinas Tenaga Kerja Barito Timur
# Update file ini untuk menambah/mengubah informasi layanan

KNOWLEDGE_BASE = {
    # Informasi Umum
    "pengantar": "Selamat datang di Layanan Chatbot Dinas Tenaga Kerja Barito Timur. Silakan ajukan pertanyaan seputar layanan kami.",
    
    # Kartu Kuning
    "kartu kuning": {
        "judul": "Syarat Pengajuan Kartu Kuning",
        "konten": """
1. Fotokopi KTP yang masih berlaku
2. Pas foto 3x4 (2 lembar, background merah)
3. Surat pengantar dari kelurahan/desa
4. Fotokopi ijazah terakhir yang dilegalisir
5. Surat keterangan pengalaman kerja (jika ada)
6. Mengisi formulir pendaftaran di loket pelayanan
"""
    },
    
    # Jam Operasional
    "jam operasional": {
        "judul": "Jam Pelayanan Dinas",
        "konten": """
🕒 Pelayanan Offline:
Senin-Kamis: 08.00 - 14.00 WIB
Jumat: 08.00 - 11.00 WIB

🕒 Pelayanan Online (Chatbot):
24 Jam setiap hari
"""
    },
    
    # Lokasi
    "lokasi": {
        "judul": "Lokasi Kantor Dinas",
        "konten": """
📍 Kantor Dinas Tenaga Kerja Barito Timur
Jl. Tjilik Riwut KM 5, Tamiang Layang, Kalimantan Tengah

🗺️ Maps: https://maps.app.goo.gl/xxxxx

📞 Telp: 0538-1234567
✉️ Email: diskertrans.bartim@gmail.com
"""
    },
    
    # Pelatihan Kerja
    "pelatihan": {
        "judul": "Program Pelatihan Gratis",
        "konten": """
Berikut program pelatihan yang tersedia:
1. Teknisi Handphone (2 bulan)
2. Menjahit dan Bordir (1 bulan)
3. Las Dasar (1 bulan)
4. Tata Rias Pengantin (1 bulan)
5. Komputer Administrasi Perkantoran (3 bulan)

📋 Syarat Pendaftaran:
- Warga Barito Timur
- Usia 18-45 tahun
- Fotokopi KTP
- Pas foto 3x4 (2 lembar)

🚀 Pendaftaran: Via WhatsApp ini atau langsung ke kantor dinas
"""
    },
    
    # Lowongan Kerja
    "lowongan": {
        "judul": "Informasi Lowongan Kerja",
        "konten": """
Untuk melihat lowongan kerja terbaru di Barito Timur:
1. Kunjungi kantor kami setiap hari kerja
2. Cek website resmi: https://disnakertrans.bartimkab.go.id/lowongan
3. Bergabung dengan grup Telegram: https://t.me/lowongan_bartim

📢 Update terbaru (Juni 2025):
- PT. Sawit Makmur: Operator Pabrik (10 orang)
- Hotel Tamiang: Resepsionis (3 orang)
- SPBU Tamiang: Kasir (2 orang)
"""
    },
    
    # Bansos Ketenagakerjaan
    "bansos": {
        "judul": "Bantuan Sosial Ketenagakerjaan",
        "konten": """
Program bantuan yang tersedia:
1. BLT Kartu Prakerja
2. Bantuan Pelatihan Vokasi Gratis
3. Program Padat Karya Tunai
4. Bantuan Usaha Mikro

📋 Persyaratan umum:
- Warga Barito Timur
- Berdomisili di wilayah Bartim
- Berada di keluarga pra-sejahtera

ℹ️ Info lengkap: https://bansos.bartimkab.go.id
"""
    }
}

# Fungsi untuk mencari jawaban dari basis pengetahuan
def cari_jawaban(pertanyaan):
    pertanyaan = pertanyaan.lower()
    
    # Cek pertanyaan langsung
    for keyword, data in KNOWLEDGE_BASE.items():
        if keyword in pertanyaan:
            return f"*{data['judul']}*\n\n{data['konten']}"
    
    # Cek dengan pola pertanyaan umum
    if any(k in pertanyaan for k in ["syarat", "kartu kuning", "ak1"]):
        return f"*{KNOWLEDGE_BASE['kartu kuning']['judul']}*\n\n{KNOWLEDGE_BASE['kartu kuning']['konten']}"
    
    if any(k in pertanyaan for k in ["jam", "buka", "pelayanan"]):
        return f"*{KNOWLEDGE_BASE['jam operasional']['judul']}*\n\n{KNOWLEDGE_BASE['jam operasional']['konten']}"
    
    if any(k in pertanyaan for k in ["lokasi", "alamat", "kantor", "map"]):
        return f"*{KNOWLEDGE_BASE['lokasi']['judul']}*\n\n{KNOWLEDGE_BASE['lokasi']['konten']}"
    
    if any(k in pertanyaan for k in ["pelatihan", "kursus", "vokasi"]):
        return f"*{KNOWLEDGE_BASE['pelatihan']['judul']}*\n\n{KNOWLEDGE_BASE['pelatihan']['konten']}"
    
    if any(k in pertanyaan for k in ["lowongan", "pekerjaan", "loker"]):
        return f"*{KNOWLEDGE_BASE['lowongan']['judul']}*\n\n{KNOWLEDGE_BASE['lowongan']['konten']}"
    
    if any(k in pertanyaan for k in ["bansos", "bantuan", "prakerja"]):
        return f"*{KNOWLEDGE_BASE['bansos']['judul']}*\n\n{KNOWLEDGE_BASE['bansos']['konten']}"
    
    return None
