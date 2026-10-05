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
Buka terminal/Command Prompt dan jalankan perintah berikut untuk menginstal pustaka yang dibutuhkan:

```bash
pip install paddlepaddle
pip install paddleocr
pip install pdf2image Pillow shapely numpy