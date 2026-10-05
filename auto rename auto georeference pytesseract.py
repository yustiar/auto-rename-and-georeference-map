# -*- coding: utf-8 -*-

import os
import json
import re
import shutil
from pathlib import Path
from pdf2image import convert_from_path
import numpy as np
import pytesseract
from PIL import Image, ImageOps
from shapely.geometry import Polygon

_GJ_CACHE = {}

# ==========================================
# KONFIGURASI PATH
# ==========================================
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# ==========================================
# PADDLEOCR (CADANGAN) - dimuat hanya saat dibutuhkan
# ==========================================
_PADDLE_MODEL = None
_PADDLE_GAGAL_MUAT = False   # jika sekali gagal dimuat, jangan dicoba lagi tiap halaman

def _dapatkan_paddle():
    """Muat PaddleOCR sekali saja, hanya ketika Tesseract gagal membaca halaman."""
    global _PADDLE_MODEL, _PADDLE_GAGAL_MUAT
    if _PADDLE_MODEL is not None:
        return _PADDLE_MODEL
    if _PADDLE_GAGAL_MUAT:
        return None
    try:
        print("    -> Memuat PaddleOCR (cadangan). Harap tunggu sebentar...")
        from paddleocr import PaddleOCR
        _PADDLE_MODEL = PaddleOCR(
            lang='en',
            enable_mkldnn=False,                 # menghindari error oneDNN/PIR
            use_doc_orientation_classify=False,  # rotasi ditangani sendiri
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
        print("    -> PaddleOCR berhasil dimuat.")
    except Exception as e:
        _PADDLE_GAGAL_MUAT = True
        print(f"    -> [PERINGATAN] PaddleOCR gagal dimuat, cadangan dinonaktifkan: {e}")
        return None
    return _PADDLE_MODEL

def _teks_dari_hasil_paddle(hasil):
    """Ambil teks dari keluaran PaddleOCR (format 3.x: dict 'rec_texts'; format 2.x: list bersarang)."""
    baris = []
    for res in hasil or []:
        try:
            teks = res['rec_texts']
        except (KeyError, TypeError, IndexError):
            teks = None
        if teks is not None:
            baris.extend(teks)
        elif isinstance(res, list):  # format lama 2.x
            for line in res:
                try:
                    baris.append(line[1][0])
                except (IndexError, TypeError):
                    pass
    return "\n".join(baris)

# ==========================================
# FUNGSI 1: MEMECAH PDF MENJADI GAMBAR
# ==========================================
def ekstrak_pdf_ke_gambar(pdf_path, dpi=300):
    print(f"  -> Mengekstrak halaman dari {pdf_path.name}...")
    pages = convert_from_path(str(pdf_path), dpi=dpi)
    return pages

def muat_geojson(path):
    if path not in _GJ_CACHE:
        with open(path) as f:
            _GJ_CACHE[path] = json.load(f)
    return _GJ_CACHE[path]

VALID_IDS = set()
def siapkan_valid_ids(path):
    gj = muat_geojson(path)
    for ft in gj['features']:
        v = ft['properties'].get('idsubsls')
        if v:
            VALID_IDS.add(str(v))

# ---------- pencocokan ID yang toleran salah baca ----------
def _hamming(a, b):
    return sum(x != y for x, y in zip(a, b)) if len(a) == len(b) else 99

_KOREKSI = str.maketrans({'O': '0', 'o': '0', 'I': '1', 'l': '1', '|': '1',
                         'S': '5', 'B': '8', 'Z': '2'})

def cocokkan_id(teks, toleransi=2):
    kandidat = []
    for baris in teks.splitlines():
        s = re.sub(r'\D', '', baris.translate(_KOREKSI))
        for i in range(len(s) - 15):
            kandidat.append(s[i:i+16])
    for w in kandidat:
        if w in VALID_IDS:
            return w
    for w in kandidat:
        if _hamming(w[:4], '3316') > 1:
            continue
        dekat = [v for v in VALID_IDS if _hamming(w, v) <= toleransi]
        if len(dekat) == 1:
            return dekat[0]
    if not VALID_IDS:
        for w in kandidat:
            if re.fullmatch(r'3316\d{12}', w):
                return w
    return None

# ---------- OCR satu gambar: TESSERACT ----------
def dapatkan_id_dari_gambar_tesseract(image):
    w, h = image.size
    for cw, ch in [(1200, 350), (1800, 600)]:
        crop = image.crop((max(0, w - cw), 0, w, min(h, ch)))
        gray = ImageOps.autocontrast(crop.convert('L'))
        gray = ImageOps.expand(gray, border=30, fill=255)
        varian = [gray] + [gray.point(lambda p, t=t: 255 if p > t else 0)
                           for t in (120, 150, 180)]
        for v in varian:
            for cfg in ('--psm 6 -c tessedit_char_whitelist=0123456789',
                        '--psm 11 -c tessedit_char_whitelist=0123456789'):
                teks = pytesseract.image_to_string(v, config=cfg)
                hasil = cocokkan_id(teks)
                if hasil:
                    return hasil
    return None

# ---------- OCR satu gambar: PADDLEOCR (cadangan) ----------
def dapatkan_id_dari_gambar_paddle(image):
    model = _dapatkan_paddle()
    if model is None:
        return None

    w, h = image.size
    for cw, ch in [(1200, 350), (1800, 600)]:
        crop = image.crop((max(0, w - cw), 0, w, min(h, ch)))
        img_array = np.array(crop.convert('RGB'))

        hasil_ocr = model.predict(img_array)
        teks_gabungan = _teks_dari_hasil_paddle(hasil_ocr)

        hasil = cocokkan_id(teks_gabungan)
        if hasil:
            return hasil
    return None

# ---------- rotasi bertahap (dipakai untuk kedua engine) ----------
def _buat_rotasi(gambar):
    return [
        (0,   gambar),
        (90,  gambar.transpose(Image.Transpose.ROTATE_90)),
        (180, gambar.transpose(Image.Transpose.ROTATE_180)),
        (270, gambar.transpose(Image.Transpose.ROTATE_270)),
    ]

def baca_id_dengan_rotasi(gambar, halaman_idx, current_folder):
    rotasi = _buat_rotasi(gambar)

    # TAHAP 1: Tesseract, rotasi 0 -> 90 -> 180 -> 270
    for sudut, img in rotasi:
        id_terbaca = dapatkan_id_dari_gambar_tesseract(img)
        if id_terbaca:
            if sudut:
                print(f"    -> ID terdeteksi pada rotasi {sudut} derajat (Tesseract).")
            return id_terbaca, img

    # TAHAP 2: PaddleOCR, mulai lagi dari rotasi 0 -> 90 -> 180 -> 270
    print("    -> Tesseract gagal di semua rotasi. Mencoba PaddleOCR dari rotasi awal...")
    for sudut, img in rotasi:
        id_terbaca = dapatkan_id_dari_gambar_paddle(img)
        if id_terbaca:
            print(f"    -> ID terdeteksi pada rotasi {sudut} derajat (PaddleOCR).")
            return id_terbaca, img

    # Gagal total: simpan crop 4 rotasi untuk debug
    for sudut, img in rotasi:
        w, h = img.size
        img.crop((max(0, w - 1800), 0, w, 600)).save(
            os.path.join(current_folder, f"GAGAL_OCR_hal{halaman_idx}_rot{sudut}.jpg"), 'JPEG')
    print(f"    -> [DEBUG] Gagal (Tesseract + PaddleOCR). 4 crop rotasi disimpan di {current_folder}")
    return None, gambar

# ==========================================
# FUNGSI 4: CEK ORIENTASI DARI GEOJSON & ROTASI FINAL
# ==========================================
def sesuaikan_orientasi(image, id_wilayah, path_geojson):
    with open(path_geojson) as f:
        gj = json.load(f)
        
    target_orientasi = 'landscape'
    
    for feature in gj['features']:
        if feature['properties'].get('idsubsls') == id_wilayah:
            poly = Polygon(feature['geometry']['coordinates'][0][0])
            minX, minY, maxX, maxY = poly.bounds
            deltaX = maxX - minX
            deltaY = maxY - minY
            
            if deltaX < deltaY:
                target_orientasi = 'portrait'
            else:
                target_orientasi = 'landscape'
            break
            
    width, height = image.size
    current_orientasi = 'portrait' if width < height else 'landscape'
    
    if current_orientasi != target_orientasi:
        print(f"    -> Merotasi gambar {id_wilayah} ke {target_orientasi} untuk layout peta...")
        image = image.rotate(90, expand=True)
        
    return image

# ==========================================
# FUNGSI 5: GEOREFERENCE (GENERATE JGW)
# ==========================================
def generate_jgw(image_path, path_geojson, id_wilayah):
    img = Image.open(image_path)
    width, height = img.size
    
    orientation = 'landscape'
    if width < height:
        orientation = 'portrait'
        
    with open(path_geojson) as f:
        gj = json.load(f)
        
    idx = 0
    for i in range(len(gj['features'])):
        if gj['features'][i]['properties'].get('idsubsls') == id_wilayah:
            idx = i
            break
            
    poly = Polygon(gj['features'][idx]['geometry']['coordinates'][0][0])
    minX, minY, maxX, maxY = poly.bounds
    
    deltaX = maxX - minX
    deltaY = maxY - minY
    jgw = []   
    
    if(deltaX >= deltaY):
        width = ((305-5.4*2)/400)*width
        height = ((254-5.4*2)/283)*height
        scaleX = round(deltaX/width, 13)
        scaleY = round(deltaY/height, 13)
        
        if(deltaY/deltaX <= height/width):
            scale = scaleX
        else:
            scale = scaleY
            
        if(orientation == 'landscape'):
            A = scale
            B = 0
            C = 0
            D = -1*(float(scale))
            E = round(minX+(maxX-minX)/2-(A * (width - 1) / 2 + (B * float(height - 1)) / 2)-((13+5.6)/299)*width*scale, 13)
            F = round(minY+(maxY-minY)/2-(C * (width - 1) / 2 + (D * float(height - 1)) / 2)+((15+5.4)/299)*width*scale, 13)
        else:
            A = 0
            B = scale
            C = scale
            D = 0
            E = round(minX+(maxX-minX)/2-(A * (width - 1) / 2 + (B * float(height - 1)) / 2)-((39+5.6)/299)*width*scale, 13)
            F = round(minY+(maxY-minY)/2-(C * (width - 1) / 2 + (D * float(height - 1)) / 2)+((1+5.1)/299)*width*scale, 13)
            
        jgw = [A, B, C, D, E, F]
            
    else:
        width = ((305-5.4*2)/400)*width
        height = ((256-5.4*2)/283)*height
        scaleX = round(deltaX/width, 13)
        scaleY = round(deltaY/height, 13)
        
        if((deltaX/deltaY) <= (width/height)):
            scale = scaleY
        else:
            scale = scaleX
    
        if(orientation == 'landscape'):
           A = 0
           B = -1*(float(scale))
           C = -1*(float(scale))
           D = 0
           E = round(minX+(maxX-minX)/2-(A * (width - 1) / 2 + (B * float(height - 1)) / 2)+((15+5.4)/299)*width*scale, 13)
           F = round(minY+(maxY-minY)/2-(C * (width - 1) / 2 + (D * float(height - 1)) / 2)+((11+5.4)/299)*width*scale, 13)
        else:
            A = scale
            B = 0
            C = 0
            D = -1*(float(scale))
            E = round(minX+(maxX-minX)/2-(A * (width - 1) / 2 + (B * float(height - 1)) / 2)+((1+5.6)/299)*width*scale, 13)
            F = round(minY+(maxY-minY)/2-(C * (width - 1) / 2 + (D * float(height - 1)) / 2)+((36+5.4)/299)*width*scale, 13)
            
        jgw = [A, B, C, D, E, F]
        
    return [("{:.13f}".format(round(val, 13))) for val in jgw]

# ==========================================
# EKSEKUSI UTAMA (MAIN LOOP)
# ==========================================
def proses_peta(target_dir='',
                geojson_file='',
                mode_jgw=1,
                jgw_source_dir='',
                dpi=300):
    
    # Validasi awal GeoJSON
    ada_geojson = os.path.exists(geojson_file)
    if ada_geojson:
        siapkan_valid_ids(geojson_file)
    else:
        print("GeoJSON tidak ditemukan, OCR hanya memakai pola regex mentah.")

    if mode_jgw == 1 and not ada_geojson:
        print("ERROR: Mode 1 membutuhkan file GeoJSON untuk generate JGW. Proses dibatalkan.")
        return

    jgw_source_index = {}
    if mode_jgw == 3:
        if not os.path.exists(jgw_source_dir):
            print(f"ERROR: Folder sumber JGW tidak ditemukan di {jgw_source_dir}")
            return
        print(f"Memindai file JGW di {jgw_source_dir}...")
        for p in Path(jgw_source_dir).rglob("*.jgw"):
            jgw_source_index[p.name] = p
        print(f"-> Ditemukan {len(jgw_source_index)} file JGW siap disalin.")

    target_path = Path(target_dir)
    semua_pdf = list(target_path.rglob('*.pdf'))
    if not semua_pdf:
        print(f"Tidak ada file PDF ditemukan di {target_dir} maupun subfoldernya.")
        return

    # ==============================================================
    # MEKANISME FILTER: Kelompokkan PDF berdasarkan folder terkecil
    # ==============================================================
    folder_ke_pdf = {}
    for pdf_path in semua_pdf:
        folder = pdf_path.parent
        if folder not in folder_ke_pdf:
            folder_ke_pdf[folder] = []
        folder_ke_pdf[folder].append(pdf_path)

    folder_untuk_diproses = []
    skipped_folders = []

    for folder, list_pdf in folder_ke_pdf.items():
        if (folder / "rekap_proses.txt").exists():
            skipped_folders.append(folder)
        else:
            folder_untuk_diproses.append((folder, list_pdf))

    if skipped_folders:
        print(f"\n[INFO] Melewati {len(skipped_folders)} folder desa (Sudah selesai sebelumnya):")
        for f in sorted(skipped_folders):
            print(f"  -> Skip: {f.name}")

    if not folder_untuk_diproses:
        print("\n[INFO] Semua subfolder desa sudah memiliki rekap_proses.txt.")
        print("Tidak ada folder baru untuk diproses. Program berhenti.")
        return

    teks_mode = {1: "Generate By Code", 2: "Hanya JPG (Skip JGW)", 3: "Copy dari Folder Sumber"}
    print(f"\nMenemukan {len(folder_untuk_diproses)} subfolder desa BARU. Mode JGW: {teks_mode.get(mode_jgw, 'Unknown')}")

    # ==============================================================
    # PROSES PER FOLDER (Bukan per PDF secara acak)
    # ==============================================================
    for folder, list_pdf in folder_untuk_diproses:
        print("\n" + "="*50)
        print(f"MULAI PROSES FOLDER DESA: {folder.name}")
        print(f"Lokasi: {folder}")
        print(f"Jumlah PDF: {len(list_pdf)}")
        print("="*50)

        rekap = {"berhasil": 0, "gagal": 0, "jgw": 0, "gagal_hal": [], "error_count": 0}

        for pdf_path in list_pdf:
            print(f"\n=== Memproses Dokumen: {pdf_path.name} ===")
            halaman_gambar = ekstrak_pdf_ke_gambar(pdf_path, dpi=dpi)

            for idx, img in enumerate(halaman_gambar):
                hal_num = idx + 1
                print(f"  -> Memeriksa halaman {hal_num}...")

                # 1. OCR dengan rotasi bertahap (Tesseract, lalu PaddleOCR jika gagal)
                id_wilayah, img = baca_id_dengan_rotasi(img, hal_num, folder)
                
                if not id_wilayah:
                    rekap["gagal"] += 1
                    rekap["gagal_hal"].append(f"{pdf_path.name} hal {hal_num}")
                    rekap["error_count"] += 1
                    
                    error_nama = f"ERROR_RENAME_{rekap['error_count']}.jpg"
                    error_path = os.path.join(folder, error_nama)
                    img.save(error_path, 'JPEG')
                    
                    print(f"    -> GAGAL OCR: ID tidak terbaca. Halaman utuh disimpan sebagai {error_nama}")
                    continue

                print(f"    -> ID Terbaca: {id_wilayah}")
                rekap["berhasil"] += 1

                # 2. Orientasi menurut GeoJSON
                if mode_jgw in [1, 3] and ada_geojson:
                    img = sesuaikan_orientasi(img, id_wilayah, geojson_file)

                # 3. Simpan JPG dengan tambahan _WSS
                jpg_nama = f"{id_wilayah}_WSS.jpg"
                jpg_path = os.path.join(folder, jpg_nama)
                img.save(jpg_path, 'JPEG')
                print(f"    -> Tersimpan: {jpg_nama}")

                # 4. Handle JGW berdasarkan Mode
                jgw_nama = f"{id_wilayah}_WSS.jgw"
                jgw_path = os.path.join(folder, jgw_nama)
                
                if mode_jgw == 1:
                    jgw_data = generate_jgw(jpg_path, geojson_file, id_wilayah)
                    with open(jgw_path, 'w') as f:
                        for item in jgw_data:
                            f.write("%s\n" % item)
                    rekap["jgw"] += 1
                    print(f"    -> World file {jgw_nama} berhasil dibuat (Generate).")
                    
                elif mode_jgw == 3:
                    if jgw_nama in jgw_source_index:
                        shutil.copy2(jgw_source_index[jgw_nama], jgw_path)
                        rekap["jgw"] += 1
                        print(f"    -> World file {jgw_nama} berhasil disalin dari sumber.")
                    else:
                        print(f"    -> [PERINGATAN] World file {jgw_nama} TIDAK DITEMUKAN di folder sumber.")

        # Buat TXT Rekap SETELAH semua PDF di folder desa ini selesai dieksekusi
        pesan = (
            f"REKAPITULASI PEMROSESAN PETA\n"
            f"Folder: {folder.name}\n"
            f"Mode JGW: {teks_mode.get(mode_jgw, 'Unknown')}\n"
            f"- Berhasil Diekstrak: {rekap['berhasil']} halaman\n"
            f"- JGW Diselesaikan: {rekap['jgw']} file\n"
            f"- Gagal Terbaca OCR: {rekap['gagal']} halaman (tersimpan sbg ERROR_RENAME)\n"
        )
        if rekap["gagal_hal"]:
            pesan += "- Daftar gagal:\n" + "\n".join(f"    * {x}" for x in rekap["gagal_hal"]) + "\n"
            
        print(f"\n[SELESAI] Folder {folder.name}. Membuat rekap_proses.txt...")
        with open(os.path.join(folder, "rekap_proses.txt"), 'w', encoding='utf-8') as f_txt:
            f_txt.write(pesan)

    print("\nPROSES SELESAI SELURUHNYA!")

# CONTOH PEMANGGILAN (Ubah parameter sesuai kebutuhan Anda)
TARGET_DIR = r'\\192.168.1.133\scan\masukkan hasil scan jpeg ke sini sesuai kec dan desanya\070_JIKEN'
GEOJSON_FILE = r'D:\2026\SE2026\SCAN\FINAL_SLS_3316_2025sm1.geojson'
jgwlayout_source_dir = r'D:\2026\Layout Peta WAWBWSWSS-2025\Result Peta WS'

proses_peta(target_dir=TARGET_DIR,
            geojson_file=GEOJSON_FILE,
            mode_jgw=3, 
            jgw_source_dir=jgwlayout_source_dir)