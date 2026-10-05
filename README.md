
```markdown
# Auto Rename & Georeference Peta Scan (PaddleOCR)

Script Python ini dirancang untuk mengotomatisasi pemrosesan dokumen PDF hasil scan peta (seperti peta SLS/Wilkerstat untuk SE2026). Script ini membaca ID unik dari peta hasil *scan* menggunakan teknologi AI (**PaddleOCR**), menyesuaikan rotasi dan orientasinya berdasarkan data spasial (**GeoJSON**), lalu menyimpannya dalam format gambar (`.jpg`) berserta *World File* (`.jgw`) agar siap digunakan di *software* SIG seperti QGIS atau ArcGIS.

## ✨ Fitur Utama

- **AI-Powered OCR (PaddleOCR):** Menggunakan *Deep Learning* untuk membaca ID wilayah (16 digit, diawali '3316') dengan tingkat akurasi tinggi, bahkan pada peta dengan *background noise* yang rumit.
- **Smart Rotation & Cropping:** Secara otomatis merotasi gambar (0°, 90°, 180°, 270°) untuk menemukan posisi teks ID yang tepat.
- **Fuzzy Matching & Validasi GeoJSON:** Memiliki toleransi salah baca karakter (misal huruf 'O' terbaca sebagai angka '0') dan mencocokkannya langsung dengan atribut `idsubsls` di file GeoJSON.
- **Auto-Orientation:** Menyesuaikan bentuk peta (Landscape/Portrait) dengan menghitung *bounding box* geometri polygon wilayah dari GeoJSON.
- **Manajemen Georeferencing Fleksibel:** Menyediakan 3 mode *World File* (JGW):
  1. Generate otomatis menggunakan perhitungan koordinat dari GeoJSON.
  2. Hanya ekstrak JPG (tanpa JGW).
  3. Salin (Copy) file JGW presisi dari folder *layout* master/sumber.
- **Incremental Processing (Resume-able):** Sangat cocok untuk pemindaian yang berjalan secara kontinu (terus-menerus). Script akan otomatis **melewati (skip) folder desa** yang sudah selesai diproses (ditandai dengan adanya file `rekap_proses.txt`).
- **Error Handling:** Jika ID gagal dibaca oleh OCR, halaman tetap disimpan secara utuh dengan nama `ERROR_RENAME_X.jpg` untuk dievaluasi/di-rename secara manual.

## 🛠️ Prasyarat & Instalasi

### 1. Kebutuhan Sistem
- **Python 3.8** atau yang lebih baru.
- Sistem Operasi Windows (Bisa dimodifikasi untuk Linux/Mac).
- **Poppler for Windows**: Wajib diinstal agar pustaka `pdf2image` dapat mengekstrak PDF.
  - Unduh Poppler Windows [di sini](https://github.com/oschwartz10612/poppler-windows/releases/).
  - Ekstrak dan tambahkan path folder `bin` Poppler ke dalam *Environment Variables* (PATH) Windows Anda.

### 2. Instalasi Library
Buka terminal/Command Prompt (atau Anaconda Prompt) dan jalankan perintah berikut untuk menginstal pustaka yang dibutuhkan:

```bash
pip install paddlepaddle
pip install paddleocr
pip install pdf2image Pillow shapely numpy

```

> **Catatan Windows:** Script ini sudah dilengkapi *bypass internal bug* pada sistem OneDNN/PIR PaddlePaddle untuk penggunaan CPU di Windows (menggunakan `os.environ` dan `paddle.set_flags()`), sehingga bebas dari *crash* saat inisialisasi.

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

### Pilihan Parameter `mode_jgw`:

* `mode_jgw=1`: Script akan menghitung dan men-generate file `.jgw` secara matematis dari *bounding box* GeoJSON.
* `mode_jgw=2`: Script hanya mengekstrak dan me-rename file gambar menjadi `_WSS.jpg` (Lewati pembuatan JGW).
* `mode_jgw=3`: Script mencari nama file JGW yang cocok dari folder `jgw_source_dir` (dan subfoldernya), lalu menyalinnya ke folder tujuan. Pencarian menggunakan metode *caching index* sehingga sangat cepat.

## 📁 Struktur Direktori & Output

**Sebelum Dijalankan:**

```text
[TARGET_DIR]
├── 001_DESA_A/
│   ├── SCAN_PETA_1.pdf (berisi beberapa halaman)
│   └── SCAN_PETA_2.pdf
└── 002_DESA_B/
    └── SCAN_PETA_3.pdf

```

**Setelah Dijalankan:**

```text
[TARGET_DIR]
├── 001_DESA_A/
│   ├── SCAN_PETA_1.pdf
│   ├── 3316123456789001_WSS.jpg      # Gambar yang terdeteksi
│   ├── 3316123456789001_WSS.jgw      # World file
│   ├── ERROR_RENAME_1.jpg            # Halaman gagal OCR
│   └── rekap_proses.txt              # Flag penanda folder selesai
└── 002_DESA_B/
    └── ...

```

> 💡 **Tips:** Jika script dijalankan ulang (Re-run), folder `001_DESA_A` akan otomatis dilewati karena keberadaan `rekap_proses.txt`, menghemat waktu *processing* secara drastis saat ada *scan* dokumen baru.

```

```
