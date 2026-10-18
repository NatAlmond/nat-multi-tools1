# Nat-Multi Tools v4

All-In-One toolkit: Downloader · Comic (All Sources) · Anime · Novel · Drama · Movie · GIF · AI  
**By: Nat🥜**

---

## Yang diperbaiki di v4

| Area | Perbaikan |
|------|-----------|
| **GIF** | Tenor/Giphy dihapus → **Gifukai** (tanpa API key) |
| **YouTube** | Hanya **Premium / Admin** |
| **AI Chat** | Gemini **3.8 Flash** (+ 3.6 / 2.5 fallback), Groq **Llama 3.3 70B** |
| **AI Image** | **Nano Banana 2.1** (+ fallback) |
| **Comic** | Mode **All Sources** + label PROJECT / KOMIK / MANHWA |
| **Comic Premium** | Shinigami, Manhwa Desu |
| **Anime** | Gabungan Otakudesu + Anoboy; **Samehadaku = Premium** |
| **Genre** | Filter benar-benar memfilter hasil |
| **Riwayat** | Comic / Anime / Novel tersimpan & bisa dibuka lagi |
| **Limit** | Free vs Premium vs Admin (lihat tabel) |
| **Banner** | 3 GIF bergeser tiap 5 detik |
| **Admin** | Verifikasi server-side hash + kode Premium sekali pakai |

---

## Batasan Free / Premium / Admin

| Fitur | Free | Premium | Admin |
|-------|------|---------|-------|
| AI Chat / hari | 30 | 200 | ∞ |
| AI Image / hari | 5 | 40 | ∞ |
| Download / hari | 8 | 50 | ∞ |
| YouTube download | ❌ | ✅ | ✅ |
| Samehadaku | ❌ | ✅ | ✅ |
| Shinigami / Manhwa Desu | ❌ | ✅ | ✅ |
| Generate kode Premium | ❌ | ❌ | ✅ |

Premium dibatalkan → kode lama **tidak bisa dipakai lagi**.

---

## Struktur file (WAJIB rename)

```
nat-multi-tools/
├── index.html
├── main.py
├── requirements.txt
├── vercel.json
├── README.md
├── banner1.gif          # opsional
├── banner2.gif
└── banner3.gif
```

File di chat yang bernama `index-5.html` / `main-2-2.py` **harus di-rename** jadi di atas.

---

## Langkah deploy lengkap

### 1. Amankan API key (penting)

Key yang pernah dikirim di chat dianggap bocor.

1. **Groq** → console.groq.com → hapus key lama → Create baru  
2. **Gemini** → aistudio.google.com/apikey → hapus / regenerate  

Simpan key baru hanya di Vercel Environment Variables.

### 2. Upload ke GitHub

1. github.com → **New repository** → nama bebas → Public → Create  
2. **Upload files** → pilih:
   - `index.html`
   - `main.py`
   - `requirements.txt`
   - `vercel.json`
   - `README.md`  
3. Commit  

### 3. Banner carousel (3 GIF)

1. Siapkan 3 file GIF  
2. Upload ke **root** repo dengan nama **persis**:
   - `banner1.gif`
   - `banner2.gif`
   - `banner3.gif`  
3. Commit  

Situs akan menampilkan ketiganya bergantian tiap 5 detik.  
Kalau belum ada, muncul placeholder.

### 4. Deploy Vercel

1. vercel.com → login GitHub  
2. **Add New → Project** → pilih repo  
3. Framework: **Other**  
4. **Environment Variables**:

| Name | Wajib | Keterangan |
|------|-------|------------|
| `GROQ_API_KEY` | Ya (AI Chat) | console.groq.com |
| `GEMINI_API_KEY` | Ya (Chat + Image) | aistudio.google.com |

5. **Deploy** → tunggu Ready → buka URL  

### 5. Aktifkan Admin

1. Tab **Secret**  
2. Masukkan: `PEANUTSBUTTERCUP`  
3. Badge **ADMIN** (biru + pelangi) muncul  
4. Tab **Admin** → pilih tanggal expiry → **Generate Kode Premium**  
5. Berikan kode ke user (sekali pakai)

---

## Fitur per tab

### Downloader
- TikTok, Instagram, Facebook, X, dll (yt-dlp)
- **YouTube = Premium**
- Batal request + preview video/audio di web
- Limit harian sesuai role

### Comic
- **All Sources** menggabungkan Komiku, Kiryuu, Komikstation, Westmanga, Mangakita
- Label: PROJECT / KOMIK / MANHWA
- Shinigami · Manhwa Desu · Omega = Premium (pesan kunci khusus)
- Filter genre benar memfilter
- Sinopsis + daftar chapter + reader gambar
- **Riwayat baca** tersimpan

### Anime
- All = Otakudesu + Anoboy
- Samehadaku = Premium
- Sinopsis + episode + player embed
- Riwayat tonton

### Novel
- WB Novel (ID)
- Riwayat baca chapter

### Drama / Movie
- Bukan player streaming ilegal

### GIF
- **Gifukai** — tanpa API key
- Action: hug, kiss, cry, dance, dll
- Download + salin URL (bahan edit)

### AI Chat
- Groq Llama 3.3 70B
- Gemini 3.6 Flash (fallback 2.5 / 2.0)

### AI Image
- Nano Banana 2.1 (fallback model image Gemini lain)

---

## Source pihak ketiga (bisa down)

Comic & Anime memakai API/scrape komunitas (Sanka, Wajik, dll).  
Domain sering pindah → kalau kosong, coba source lain atau tunggu API hidup lagi.

Shinigami tersedia lewat Sanka (Premium di tools ini).

---

## Safelink

Endpoint `/safelink?url=...` hanya **mengikuti redirect HTTP**.  
Bukan bypass proteksi berbayar / captcha kompleks.

---

## Keamanan Admin

- Master code dicek hash di server (`/admin/verify`)
- Kode Premium **sekali pakai** + bisa expiry
- Batalkan Premium → harus minta kode baru
- Tetap **bukan** keamanan bank: localStorage bisa diedit orang mahir. Untuk produksi butuh database + login.

---

## Troubleshooting

| Masalah | Solusi |
|---------|--------|
| Halaman kosong | Pastikan file bernama `index.html` + `main.py` (bukan index-5.html) |
| AI 503 | Isi GROQ_API_KEY / GEMINI_API_KEY + Redeploy |
| GIF kosong | Cek `/gif/search?q=hug` — Gifukai harus online |
| Comic/Anime kosong | Source API down → coba source lain / All Sources |
| YouTube gagal | Sering diblok server cloud; coba platform lain |
| Banner tidak jalan | Upload banner1/2/3.gif di root |

Cek health: `https://DOMAIN-ANDA/health`

---

## Catatan hukum

Tools ini untuk edukasi. Hormati hak cipta sumber.  
Jangan hardcode API key di GitHub.

**By: Nat🥜**
