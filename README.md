# Auto Rename & Georeference Peta Scan (PaddleOCR)

Script Python untuk mengotomatisasi pemrosesan dokumen PDF hasil scan peta (seperti peta SLS/Wilkerstat untuk SE2026).

Script ini membaca ID unik dari peta hasil *scan* menggunakan **PaddleOCR**, menyesuaikan rotasi dan orientasinya berdasarkan data spasial (**GeoJSON**), lalu menyimpannya sebagai gambar (`.jpg`) beserta *World File* (`.jgw`) sehingga siap dipakai di software SIG seperti QGIS atau ArcGIS.

---

## ✨ Fitur Utama

- **AI-Powered OCR (PaddleOCR)**
  Menggunakan *deep learning* untuk membaca ID wilayah (16 digit, diawali `3316`) dengan akurasi tinggi, bahkan pada peta dengan *background noise* yang rumit.

- **Smart Rotation & Cropping**
  Merotasi gambar secara otomatis (0°, 90°, 180°, 270°) untuk menemukan posisi teks ID yang tepat.

- **Fuzzy Matching & Validasi GeoJSON**
  Toleran terhadap salah baca karakter (misalnya huruf `O` terbaca sebagai angka `0`) dan langsung mencocokkan hasilnya dengan atribut `idsubsls` pada file GeoJSON.

- **Auto-Orientation**
  Menyesuaikan bentuk peta (*landscape*/*portrait*) dengan menghitung *bounding box* geometri polygon wilayah dari GeoJSON.

- **Georeferencing Fleksibel**
  Menyediakan 3 mode *World File* (JGW), lihat bagian [Parameter `mode_jgw`](#parameter-mode_jgw).

- **Incremental Processing (Resume-able)**
  Cocok untuk pemindaian yang berjalan terus-menerus. Folder desa yang sudah selesai diproses (ditandai file `rekap_proses.txt`) akan otomatis **dilewati**.

- **Error Handling**
  Jika ID gagal dibaca OCR, halaman tetap disimpan utuh dengan nama `ERROR_RENAME_X.jpg` untuk dievaluasi atau di-rename secara manual.

---

## 🛠️ Prasyarat & Instalasi

### 1. Kebutuhan Sistem

- **Python 3.8** atau lebih baru
- Sistem operasi Windows (dapat dimodifikasi untuk Linux/Mac)
- **Poppler for Windows** — wajib agar pustaka `pdf2image` dapat mengekstrak PDF:
  1. Unduh Poppler Windows di [oschwartz10612/poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases/).
  2. Ekstrak, lalu tambahkan path folder `bin` Poppler ke *Environment Variables* (`PATH`) Windows.

### 2. Instalasi Library

Buka Terminal/Command Prompt (atau Anaconda Prompt), lalu jalankan:

```bash
pip install paddlepaddle
pip install paddleocr
pip install pdf2image Pillow shapely numpy
```

> [!NOTE]
> **Catatan Windows:** Script ini sudah dilengkapi *bypass* untuk bug internal OneDNN/PIR PaddlePaddle pada penggunaan CPU di Windows (menggunakan `os.environ` dan `paddle.set_flags()`), sehingga tidak *crash* saat inisialisasi.

---

## 🚀 Cara Penggunaan

Buka file script Python, lalu pada bagian paling bawah (`CONTOH PEMANGGILAN`), sesuaikan path direktori dengan konfigurasi server/komputer Anda:

```python
TARGET_DIR = r'\\192.168.1.133\scan\masukkan hasil scan jpeg ke sini sesuai kec dan desanya\040_KEDUNGTUBAN'
GEOJSON_FILE = r'D:\2026\SE2026\SCAN\FINAL_SLS_3316_2025sm1.geojson'
jgwlayout_source_dir = r'D:\2026\Layout Peta WAWBWSWSS-2025\Result Peta WS'

proses_peta(
    target_dir=TARGET_DIR,
    geojson_file=GEOJSON_FILE,
    mode_jgw=3,
    jgw_source_dir=jgwlayout_source_dir
)
```

### Parameter `mode_jgw`

| Nilai | Perilaku |
|:-----:|----------|
| `1` | Menghitung dan men-generate file `.jgw` secara matematis dari *bounding box* GeoJSON. |
| `2` | Hanya mengekstrak dan me-rename gambar menjadi `_WSS.jpg` (tanpa pembuatan JGW). |
| `3` | Mencari file JGW yang cocok di `jgw_source_dir` (termasuk subfolder), lalu menyalinnya ke folder tujuan. Pencarian memakai *caching index* sehingga sangat cepat. |

---

## 📁 Struktur Direktori & Output

**Sebelum dijalankan:**

```text
[TARGET_DIR]
├── 001_DESA_A/
│   ├── SCAN_PETA_1.pdf          # berisi beberapa halaman
│   └── SCAN_PETA_2.pdf
└── 002_DESA_B/
    └── SCAN_PETA_3.pdf
```

**Setelah dijalankan:**

```text
[TARGET_DIR]
├── 001_DESA_A/
│   ├── SCAN_PETA_1.pdf
│   ├── 3316123456789001_WSS.jpg # gambar yang terdeteksi
│   ├── 3316123456789001_WSS.jgw # world file
│   ├── ERROR_RENAME_1.jpg       # halaman gagal OCR
│   └── rekap_proses.txt         # penanda folder selesai
└── 002_DESA_B/
    └── ...
```

> [!TIP]
> Jika script dijalankan ulang (*re-run*), folder `001_DESA_A` akan otomatis dilewati karena adanya `rekap_proses.txt`. Ini menghemat waktu pemrosesan secara drastis ketika ada *scan* dokumen baru.
