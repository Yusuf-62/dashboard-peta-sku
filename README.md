# Dashboard Peta Potensi SKU — GitHub Pages

Versi statis untuk GitHub Pages. Python hanya berjalan lokal untuk mengubah file Excel dan GeoJSON menjadi JSON. Interaksi filter, KPI, tabel, dan peta dijalankan di browser dengan JavaScript.

## Struktur folder yang dibutuhkan

Salin folder asli milik proyek ke root folder ini, dengan struktur:

```text
Data SKU/                 # Excel per SKU (.xlsx / .xls)
Kab yang digunakan/       # GeoJSON kabupaten dan kecamatan (struktur dijelaskan di bawah) atau nama provinsi
assets/                   # Gambar logo/ikon PNG/JPG/JPEG/WebP (opsional)
index.html
scripts/export_data.py
```

File `assets/css`, `assets/js`, dan folder `data` yang ada di paket ini merupakan bagian website; jangan menimpa file CSS/JS tersebut dengan folder aset gambar lama. Letakkan logo/ikon sumber di `Assets/images/`. Script ekspor akan memasukkannya ke `data/assets.json`; versi Dash Python juga menggunakan folder yang sama sebagai sumber logo.

## 1. Buat virtual environment (opsional tetapi disarankan)

Windows CMD:

```cmd
py -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

Jika `py` tidak tersedia, gunakan `python -m venv .venv`.

## 2. Konversi Excel dan peta menjadi JSON

Letakkan file Excel per SKU ke `Data SKU/` dan GeoJSON ke `Kab yang digunakan/`, lalu jalankan dari root proyek:

```cmd
python scripts/export_data.py
```

Script membuat:

- `data/dashboard.json` — data Excel yang sudah dibersihkan dan diagregasi per SKU, depo, provinsi, kabupaten.
- `data/geojson.json` — geometri batas kabupaten/kota untuk peta Leaflet.
- `data/kecamatan_geojson.json` — geometri batas kecamatan; jika belum tersedia, file tetap dibuat dengan daftar fitur kosong.
- `data/assets.json` — gambar PNG/JPG/WebP yang ada di `assets/`, dikodekan menjadi data URI Base64 agar frontend bisa membacanya melalui JSON.

PNG tidak dikonversi menjadi data vektor JSON; isi gambar tetap gambar raster yang dienkode Base64. Jika tidak ingin manifest Base64, frontend bisa langsung memakai file PNG melalui URL. Perhatikan bahwa `assets.json` akan membesar jika berisi gambar berukuran besar.

## 3. Uji secara lokal

Jalankan server statis dari root folder proyek:

```cmd
python -m http.server 8000
```

Buka `http://localhost:8000`. Jangan membuka `index.html` langsung dengan `file://`, karena browser dapat memblokir permintaan `fetch()` untuk file JSON.

## 4. Publikasikan melalui GitHub Pages

Commit dan push website serta data yang diizinkan untuk dipublikasikan:

```cmd
git add index.html assets data scripts requirements.txt README.md .gitignore
git commit -m "Publish static SKU dashboard"
git push origin main
```

Di GitHub, buka **Settings → Pages**, pilih **Deploy from a branch**, branch `main`, folder `/(root)`, lalu **Save**. Website akan menggunakan URL GitHub Pages yang ditampilkan di pengaturan repository.

## 5. Update manual

Setiap kali ada Excel baru/perubahan data:

1. Ganti atau tambahkan file Excel di `Data SKU/`.
2. Jika batas peta berubah, perbarui GeoJSON di `Kab yang digunakan/`, dengan memisahkan file kabupaten dan kecamatan sesuai struktur berikut:
3. Jalankan `python scripts/export_data.py`.
4. Uji lokal dengan `python -m http.server 8000`.
5. Commit dan push file hasilnya.

```cmd
git add data
 git add index.html assets
 git commit -m "Update SKU dashboard data"
 git push origin main
```

## Catatan penting

- GitHub Pages hanya menjalankan file statis. Callback Python dari Dash tidak berjalan di website; interaksi yang tersedia di versi ini ditangani JavaScript.
- Data JSON, GeoJSON, dan gambar yang dipush ke repository publik dapat diunduh siapa pun. Jangan push data penjualan/pelanggan yang rahasia atau belum diizinkan untuk dipublikasikan.
- Peta menggunakan tile Carto basemap dan library Leaflet/Plotly dari CDN, sehingga pengunjung memerlukan akses internet.
- Script mempertahankan kolom yang digunakan pada dashboard asli: `DEPO`, `PROVINSI`, `KABUPATEN`, `ACT MTD`, `LY`, `AVG L3M`, `LM`, `CUST ACT`, `CUST REG`, dan `Id Pelanggan`.


### CARTO basemap API key

Basemap telah dikonfigurasi menggunakan CARTO Voyager Raster Tiles. URL tile dan API key berada di `assets/js/dashboard.js`. Karena aplikasi GitHub Pages bersifat publik, key dapat dilihat oleh pengunjung. Atur pembatasan/kuota key di layanan CARTO jika tersedia dan pantau pemakaian. Jika key pernah terungkap di tempat publik atau dicurigai disalahgunakan, rotasi key tersebut.


## Pembaruan tampilan
- Logo SNS dipusatkan di kolom kiri header dan diperbesar secukupnya.
- Metrik CA, CR, dan %CA pada kartu provinsi dibuat sebagai tiga kotak kecil terpisah.
- Untuk GitHub Pages, unggah seluruh isi folder proyek (termasuk `index.html`, `assets/`, `scripts/`, dan hasil ekspor `data/`) ke root branch `main`. `index.html` saja tidak cukup karena dashboard memerlukan file JavaScript, CSS, dan JSON.


## Filter ringkas
Header dashboard menggunakan satu baris untuk pilihan Wilayah dan pencarian SKU. Filter Kecamatan dan Depo tersedia di panel **Filter** agar area peta tetap luas. Pilihan Wilayah berisi provinsi dan kabupaten. Agar filter Kecamatan aktif, file Excel SKU harus memiliki kolom `KECAMATAN` (atau variasi nama yang setara); jika kolom itu tidak ada, filter kecamatan akan nonaktif. GeoJSON proyek ini masih berbatas kabupaten, sehingga saat memilih kecamatan angka akan terfilter ke kecamatan tetapi bentuk peta tetap menyorot kabupaten terkait.


### Struktur GeoJSON kabupaten dan kecamatan

```text
Kab yang digunakan/
├── kaltim/
│   └── batas_kabupaten.geojson
├── kalsel/
│   └── batas_kabupaten.geojson
├── kalteng/
│   └── batas_kabupaten.geojson
└── Kecamatan/
    ├── kaltim/
    │   └── batas_kecamatan.geojson
    ├── kalsel/
    │   └── batas_kecamatan.geojson
    └── kalteng/
        └── batas_kecamatan.geojson
```

Nama file boleh berbeda. Folder kecamatan harus bernama `Kecamatan`, dan subfolder provinsi harus mengandung nama/alias `kaltim`, `kalsel`, atau `kalteng`. GeoJSON kecamatan sebaiknya memiliki atribut nama kecamatan (`WADMKC` atau `KECAMATAN`) serta kabupaten/kota (`WADMKK` atau `KABUPATEN`). Pencocokan data Excel memakai kolom `PROVINSI`, `KABUPATEN`, dan `KECAMATAN`; ejaan nama wilayah harus konsisten.

Saat memilih kecamatan, peta menampilkan batas kecamatan terpilih jika geometri kecamatan tersedia dan nama kecamatan cocok dengan data Excel. Jika file geometri kecamatan belum tersedia atau nama tidak cocok, peta tetap menggunakan batas kabupaten.


## Versi Python Dash

File `dashboard_original_dash.py` adalah versi aplikasi Python Dash. Letakkan folder `Data SKU/`, `Kab yang digunakan/`, dan `Assets/images/` satu tingkat dengan file Python. Instal dependensi menggunakan `pip install -r requirements.txt`, lalu jalankan `python dashboard_original_dash.py`.

## Struktur paket

- `index.html`, `assets/css/style.css`, `assets/js/dashboard.js`: frontend website statis.
- `scripts/export_data.py`: mengubah Excel dan GeoJSON menjadi JSON untuk website statis.
- `dashboard_original_dash.py`: aplikasi Python Dash.
- `Assets/images/`: lokasi logo dan ikon sumber.
- `Data SKU/` dan `Kab yang digunakan/`: folder placeholder; masukkan data asli proyek sebelum ekspor.
