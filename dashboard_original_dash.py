# DASHBOARD INTERAKTIF EMACO2 - REGION KALIMANTAN
# Folder data otomatis dibaca relatif terhadap lokasi file Python:
#   ./Data SKU/           -> file Excel per SKU (.xlsx / .xls)
#   ./Kab yang digunakan/ -> file GeoJSON (termasuk seluruh subfolder)
# File baru di kedua folder akan terdeteksi saat dashboard dijalankan ulang.
# Jika perlu: python -m pip install pandas geopandas plotly dash

from pathlib import Path
import json, re, unicodedata, warnings, shutil
import pandas as pd
import geopandas as gpd
import plotly.graph_objects as go
import plotly.express as px
from dash import Dash, dcc, html, Input, Output

warnings.filterwarnings("ignore")

PROJECT_DIR = Path(__file__).resolve().parent
FOLDER_EXCEL_SKU = PROJECT_DIR / "Data SKU"
ROOT_GEOJSON = PROJECT_DIR / "Kab yang digunakan"

for folder_data in (FOLDER_EXCEL_SKU, ROOT_GEOJSON):
    if not folder_data.is_dir():
        raise FileNotFoundError(
            f"Folder data tidak ditemukan: {folder_data}\n"
            "Pastikan folder tersebut berada satu tingkat dengan file Python."
        )

print(f"Folder Excel SKU: {FOLDER_EXCEL_SKU}")
print(f"Folder GeoJSON:   {ROOT_GEOJSON}")

REQUIRED_COLUMNS = ["DEPO", "PROVINSI", "KABUPATEN", "ACT MTD", "LY", "AVG L3M", "LM", "CUST ACT", "CUST REG", "Id Pelanggan"]


def siapkan_data_excel(path_excel):
    df = pd.read_excel(path_excel)
    df.columns = [str(c).strip() for c in df.columns]
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Kolom wajib tidak ditemukan pada {path_excel.name}: {missing}")
    for c in ["ACT MTD", "LY", "AVG L3M", "LM", "CUST ACT", "CUST REG"]:
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", ".", regex=False), errors="coerce").fillna(0)
    df["DEPO"] = df["DEPO"].fillna("(DEPO KOSONG)").astype(str).str.strip()
    df["PROVINSI"] = df["PROVINSI"].fillna("").astype(str).str.strip()
    df["KABUPATEN"] = df["KABUPATEN"].fillna("").astype(str).str.strip()
    df["provinsi_key"] = df["PROVINSI"].map(normalisasi)
    df["kabupaten_key"] = df["KABUPATEN"].map(normalisasi)
    keys = [normalisasi(x) for x in PROVINSI_TARGET]
    return df[df["provinsi_key"].isin(keys) & df["kabupaten_key"].ne("")].copy()



FOLDER_PROVINSI = {
    "kaltim": "Kalimantan Timur",
    "kalteng": "Kalimantan Tengah",
    "kalsel": "Kalimantan Selatan",
}
PROVINSI_TARGET = list(FOLDER_PROVINSI.values())
WARNA_PROVINSI = {
    "Kalimantan Tengah": [[0, "#E8F5E9"], [0.5, "#81C784"], [1, "#1B5E20"]],
    "Kalimantan Selatan": [[0, "#E3F2FD"], [0.5, "#64B5F6"], [1, "#0D47A1"]],
    "Kalimantan Timur": [[0, "#FFFDE7"], [0.5, "#FFF176"], [1, "#F9A825"]],
}
WARNA_SOLID = {"Kalimantan Tengah": "#43A047", "Kalimantan Selatan": "#42A5F5", "Kalimantan Timur": "#FBC02D"}
BIRU = "#123F70"
HIJAU = "#16833D"
MERAH = "#E53935"

def normalisasi(teks):
    if pd.isna(teks): return ""
    teks = unicodedata.normalize("NFKD", str(teks))
    teks = "".join(c for c in teks if not unicodedata.combining(c))
    teks = teks.upper().strip()
    teks = re.sub(r"^(KABUPATEN|KAB\.|KOTA ADMINISTRASI|KOTA)\s+", "", teks)
    return re.sub(r"[^A-Z0-9]", "", teks)

# Nama SKU mengikuti nama file: "SKU EMACO2.xlsx" menjadi "EMACO2".
excel_files = sorted([*FOLDER_EXCEL_SKU.rglob("*.xlsx"), *FOLDER_EXCEL_SKU.rglob("*.xls")])
excel_files = [f for f in excel_files if not f.name.startswith("~$")]
if not excel_files:
    raise FileNotFoundError(f"Tidak ditemukan file Excel .xlsx/.xls di folder: {FOLDER_EXCEL_SKU}")

DATA_BY_SKU = {}
for excel_path in excel_files:
    sku_name = re.sub(r"^SKU\s+", "", excel_path.stem.strip(), flags=re.IGNORECASE).strip() or excel_path.stem
    try:
        DATA_BY_SKU[sku_name] = siapkan_data_excel(excel_path)
        print(f"SKU dimuat: {sku_name} ({len(DATA_BY_SKU[sku_name]):,} baris)")
    except Exception as exc:
        print(f"SKU dilewati ({excel_path.name}): {exc}")
if not DATA_BY_SKU:
    raise ValueError("Tidak ada file Excel SKU yang memiliki kolom dashboard yang sesuai.")
SKU_DEFAULT = next(iter(DATA_BY_SKU))
data = DATA_BY_SKU[SKU_DEFAULT]

# Agregasi statis per SKU: filter dashboard bekerja pada ringkasan kabupaten,
# bukan memindai ulang seluruh ~15 ribu baris setiap interaksi.
AGG_BY_SKU = {}
for _sku, _frame in DATA_BY_SKU.items():
    AGG_BY_SKU[_sku] = _frame.groupby(
        ["DEPO", "PROVINSI", "provinsi_key", "KABUPATEN", "kabupaten_key"],
        as_index=False, sort=False, dropna=False
    ).agg({
        "ACT MTD": "sum", "LY": "sum", "AVG L3M": "sum", "LM": "sum",
        "CUST ACT": "sum", "CUST REG": "sum"
    })


def angka(x):
    try: return f"{float(x):,.0f}".replace(",", ".")
    except: return "0"

def rupiah(x): return "Rp " + angka(x)

def pct(x):
    return "—" if pd.isna(x) else f"{x:+.1f}%".replace(".", ",")

def growth(act, base):
    if not base: return 0 if not act else float("nan")
    return (act / base - 1) * 100

def card(children, style=None, **kwargs):
    s = {"background":"white","border":"1px solid #D8E5F2","borderRadius":"12px",
         "padding":"13px","boxShadow":"0 2px 7px rgba(20,55,90,.05)","minWidth":"0"}
    if style: s.update(style)
    return html.Div(children, style=s, **kwargs)

def panel_title(text):
    return html.Div(text, className="panel-title", style={"background":BIRU,"color":"white","fontWeight":"700",
        "padding":"10px 13px","borderRadius":"10px 10px 0 0","fontSize":"16px"})

# --- Load GeoJSON kabupaten ---
# Mendukung nama folder pendek (kaltim) maupun nama provinsi lengkap.
ALIAS_PROVINSI = {
    "kaltim": ["KALTIM", "KALIMANTANTIMUR"],
    "kalteng": ["KALTENG", "KALIMANTANTENGAH"],
    "kalsel": ["KALSEL", "KALIMANTANSELATAN"],
}

def deteksi_provinsi(path_file):
    bagian_path = [normalisasi(part) for part in path_file.parts]
    for key, aliases in ALIAS_PROVINSI.items():
        if any(alias in bagian for alias in aliases for bagian in bagian_path):
            return key
    return None

all_geo = list(ROOT_GEOJSON.rglob("*.geojson"))
geo_files = [(f, deteksi_provinsi(f.relative_to(ROOT_GEOJSON))) for f in all_geo]
geo_files = [(f, key) for f, key in geo_files if key is not None]
if not geo_files:
    contoh = ", ".join(str(x) for x in all_geo[:5]) or "(tidak ada file .geojson)"
    raise ValueError(
        "Tidak ada file GeoJSON yang bisa dikaitkan dengan provinsi Kalimantan Timur, "
        "Kalimantan Tengah, atau Kalimantan Selatan. Pastikan file berada di dalam "
        "subfolder bernama kaltim/kalteng/kalsel atau nama provinsi lengkap. "
        f"Contoh file yang ditemukan: {contoh}"
    )

frames = []
for f, key in geo_files:
    try:
        temp = gpd.read_file(f)
        if temp.empty:
            continue
        temp["provinsi"] = FOLDER_PROVINSI[key]
        temp["sumber_file"] = f.stem
        if temp.crs is None:
            temp = temp.set_crs("EPSG:4326")
        elif temp.crs.to_epsg() != 4326:
            temp = temp.to_crs("EPSG:4326")
        frames.append(temp)
    except Exception as e:
        print(f"Gagal membaca {f.name}: {e}")
if not frames:
    raise ValueError("File GeoJSON ditemukan, tetapi tidak ada yang berhasil dibaca.")

gdf = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), geometry="geometry", crs="EPSG:4326")
name_candidates = ["WADMKK","KABUPATEN","kabupaten","NAMOBJ","name","NAME_2","NAME_3","shapeName"]
geo_name_col = next((c for c in name_candidates if c in gdf.columns), None)
gdf["kabupaten_geo"] = gdf[geo_name_col].astype(str) if geo_name_col else gdf["sumber_file"].astype(str)
gdf["provinsi_key"] = gdf["provinsi"].map(normalisasi)
gdf["kabupaten_key"] = gdf["kabupaten_geo"].map(normalisasi)
# Daftar kunci provinsi untuk menyaring GeoJSON (didefinisikan sebelum digunakan).
target_keys = [normalisasi(p) for p in PROVINSI_TARGET]
gdf = gdf[gdf["provinsi_key"].isin(target_keys)].reset_index(drop=True)
gdf["feature_id"] = gdf.index.astype(str)
# GeoJSON geometri diserialisasi satu kali saat startup, bukan setiap filter berubah.
GEOJSON_CACHE = json.loads(gdf[["feature_id", "geometry"]].to_json())
GEOJSON_FEATURE_IDS = gdf["feature_id"].astype(str).to_numpy()
GEOJSON_PROVINSI = gdf["provinsi"].to_numpy()
GEOJSON_PROVINSI_KEYS = gdf["provinsi_key"].to_numpy()
GEOJSON_KABUPATEN_KEYS = gdf["kabupaten_key"].to_numpy()
GEOJSON_KABUPATEN_NAMES = gdf["kabupaten_geo"].to_numpy()

def aggregate(df):
    return df.groupby(["provinsi_key","kabupaten_key"], as_index=False).agg(
        **{"ACT MTD":("ACT MTD","sum"),"LY":("LY","sum"),"AVG L3M":("AVG L3M","sum"),
           "LM":("LM","sum"),"CUST ACT":("CUST ACT","sum"),"CUST REG":("CUST REG","sum"),
           "UniqueCustomers":("Id Pelanggan","nunique")})

def summary_by_province(df):
    if df.empty:
        return pd.DataFrame(columns=["PROVINSI","ACT MTD","LY","AVG L3M","LM","CUST ACT","CUST REG","G_LY","G_L3M","G_LM","%CA"])
    out = df.groupby("PROVINSI", as_index=False).agg(
        **{"ACT MTD":("ACT MTD","sum"),"LY":("LY","sum"),"AVG L3M":("AVG L3M","sum"),
           "LM":("LM","sum"),"CUST ACT":("CUST ACT","sum"),"CUST REG":("CUST REG","sum")})
    out["G_LY"] = out.apply(lambda r:growth(r["ACT MTD"],r["LY"]),axis=1)
    out["G_L3M"] = out.apply(lambda r:growth(r["ACT MTD"],r["AVG L3M"]),axis=1)
    out["G_LM"] = out.apply(lambda r:growth(r["ACT MTD"],r["LM"]),axis=1)
    out["%CA"] = out.apply(lambda r:100*r["CUST ACT"]/r["CUST REG"] if r["CUST REG"] else 0,axis=1)
    return out

def make_table(df):
    if df.empty:
        return html.Div("Tidak ada data untuk filter ini.", style={"padding":"14px"})

    # Tabel detail per kabupaten, dengan nama provinsi tetap ditampilkan.
    detail = df.groupby(["PROVINSI", "KABUPATEN"], as_index=False).agg(
        **{"ACT MTD": ("ACT MTD", "sum"), "LY": ("LY", "sum"),
           "AVG L3M": ("AVG L3M", "sum"), "LM": ("LM", "sum"),
           "CUST ACT": ("CUST ACT", "sum"), "CUST REG": ("CUST REG", "sum")})
    detail["G_LY"] = detail.apply(lambda r: growth(r["ACT MTD"], r["LY"]), axis=1)
    detail["G_L3M"] = detail.apply(lambda r: growth(r["ACT MTD"], r["AVG L3M"]), axis=1)
    detail["G_LM"] = detail.apply(lambda r: growth(r["ACT MTD"], r["LM"]), axis=1)
    detail["%CA"] = detail.apply(lambda r: 100*r["CUST ACT"]/r["CUST REG"] if r["CUST REG"] else 0, axis=1)
    heads = ["Provinsi", "Kabupaten", "Sales ACT MTD", "vs LY", "vs L3M", "vs LM", "Cust Act / Reg", "%CA"]
    header = html.Tr([html.Th(x, style={"background":"#E8F1FA", "padding":"8px 6px", "fontSize":"11px",
                                         "fontWeight":"800", "position":"sticky", "top":0, "zIndex":1}) for x in heads])
    rows=[]
    for _, r in detail.sort_values(["PROVINSI", "KABUPATEN"]).iterrows():
        vals=[r["PROVINSI"], r["KABUPATEN"], angka(r["ACT MTD"]), pct(r["G_LY"]), pct(r["G_L3M"]), pct(r["G_LM"]),
              f'{angka(r["CUST ACT"])} / {angka(r["CUST REG"])}', f'{r["%CA"]:.1f}%']
        cells=[]
        for j, v in enumerate(vals):
            color = HIJAU if j in [3,4,5] and isinstance(v,str) and v.startswith("+") else (
                MERAH if j in [3,4,5] and isinstance(v,str) and v.startswith("-") else "#122C56")
            cells.append(html.Td(v, style={"padding":"7px 6px", "borderBottom":"1px solid #E7EDF4",
                "textAlign":"left" if j in [0,1] else "center", "fontSize":"11px", "color":color,
                "fontWeight":"600" if j in [1,2] else "400", "whiteSpace":"nowrap"}))
        rows.append(html.Tr(cells))
    return html.Div(html.Table([html.Thead(header), html.Tbody(rows)], style={"width":"100%", "borderCollapse":"collapse"}),
                    style={"maxHeight":"100%", "height":"100%", "overflowY":"auto", "overflowX":"auto"})

# --- App layout ---
# Logo SNS: letakkan file SNS_Group_Logo.png di folder assets proyek.
# Saat dijalankan di komputer pengguna, script juga mencoba mengambil logo dari folder yang disebutkan.
ASSETS_DIR = PROJECT_DIR / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)
LOGO_SOURCE_DIR = Path(r"D:\Peta Potensi SKU\Program\Vir_Program_Peta\Logo Icon")
SUPPORTED_LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
logo_assets = [
    p for p in ASSETS_DIR.iterdir()
    if p.is_file() and p.stem.lower() == "sns_group_logo"
    and p.suffix.lower() in SUPPORTED_LOGO_EXTENSIONS
]
if not logo_assets and LOGO_SOURCE_DIR.is_dir():
    logo_candidates = [
        p for p in LOGO_SOURCE_DIR.iterdir()
        if p.is_file() and p.stem.lower() == "sns_group_logo"
        and p.suffix.lower() in SUPPORTED_LOGO_EXTENSIONS
    ]
    if logo_candidates:
        copied_logo = ASSETS_DIR / logo_candidates[0].name
        shutil.copy2(logo_candidates[0], copied_logo)
        logo_assets = [copied_logo]

# Salin ikon KPI dari folder Logo Icon ke assets agar dapat ditampilkan oleh Dash.
ICON_FILE_ALIASES = {
    "sales": ["actual_sales", "act_sales", "sales_act"],
    "ca": ["customer_active", "customer_act"],
    "cr": ["customer_register", "customer_registered", "customer_registe", "customer_registerd"],
    "rate": ["pie_chart_percentage", "piechart_percentage", "pie_chart_percent", "pie_chart_percent age"],
}
ICON_ASSET_NAMES = {}
if LOGO_SOURCE_DIR.is_dir():
    for key, aliases in ICON_FILE_ALIASES.items():
        existing = [
            p for p in ASSETS_DIR.iterdir()
            if p.is_file() and p.suffix.lower() in SUPPORTED_LOGO_EXTENSIONS
            and p.stem.lower() in aliases
        ]
        if not existing:
            candidates = [
                p for p in LOGO_SOURCE_DIR.iterdir()
                if p.is_file() and p.suffix.lower() in SUPPORTED_LOGO_EXTENSIONS
                and p.stem.lower().replace(" ", "_") in aliases
            ]
            if not candidates:
                candidates = [
                    p for p in LOGO_SOURCE_DIR.iterdir()
                    if p.is_file() and p.suffix.lower() in SUPPORTED_LOGO_EXTENSIONS
                    and any(p.stem.lower().replace(" ", "_").startswith(alias) for alias in aliases)
                ]
            if candidates:
                target = ASSETS_DIR / candidates[0].name
                shutil.copy2(candidates[0], target)
                existing = [target]
        if existing:
            ICON_ASSET_NAMES[key] = existing[0].name

if logo_assets:
    LOGO_ASSET_NAME = logo_assets[0].name
else:
    LOGO_ASSET_NAME = "SNS_Group_Logo.png"
    print("Peringatan: SNS_Group_Logo tidak ditemukan. Letakkan file logo di folder assets proyek.")

app = Dash(__name__, assets_folder=str(ASSETS_DIR))
app.index_string = """<!DOCTYPE html>
<html>
  <head>
    {%metas%}
    <title>{%title%}</title>
    {%favicon%}
    {%css%}
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
      :root { --gap: clamp(5px, .65vw, 10px); }
      html, body { margin:0; padding:0; width:100%; height:100%; overflow:hidden; }
      body { font-family: Arial, sans-serif; }
      *, *::before, *::after { box-sizing:border-box; }
      #react-entry-point, #_dash-app-content { height:100%; min-height:0; }
      .dashboard-shell {
        width:100%; height:100vh; height:100dvh; max-height:100dvh;
        padding:clamp(4px,.45vw,7px); gap:clamp(4px,.45vw,7px); overflow:hidden;
        display:grid; grid-template-rows:auto auto minmax(0,1fr) auto;
      }
      .dashboard-header { min-height:0; padding:clamp(7px,.7vh,11px) clamp(12px,1vw,18px) !important; margin:0 !important; display:grid !important; grid-template-columns:minmax(88px, .22fr) minmax(190px, .7fr) minmax(580px, 1.9fr); align-items:center; gap:clamp(8px,1vw,16px); }\n      .header-title-block { overflow:hidden !important; }
      .header-logo-space { min-width:0; }
      .header-title-block { min-width:0; }
      .dashboard-header .eyebrow { font-size:clamp(12px,1.1vw,18px) !important; }
      .dashboard-header .region-title { font-size:clamp(18px,1.7vw,27px) !important; }
      .dashboard-header .subtitle { font-size:clamp(7px,.55vw,9px) !important; font-weight:400 !important; margin-top:2px !important; white-space:nowrap !important; overflow:hidden !important; text-overflow:ellipsis !important; max-width:100% !important; letter-spacing:0 !important; }
      .header-filter { min-width:0; padding:0 !important; background:transparent !important; border:0 !important; box-shadow:none !important; color:white; }
      .filter-title { margin-bottom:4px !important; font-size:clamp(10px,.85vw,13px) !important; color:white !important; }
      .filter-row { gap:var(--gap) !important; }
      .filter-row > div { min-width:0 !important; }
      .filter-row label { font-size:clamp(9px,.7vw,11px); color:white; }
      .Select-control, .Select__control, .dash-dropdown { min-height:30px !important; color:#145A91 !important; }\n      .Select-value-label, .Select__single-value, .Select-placeholder, .Select-option, .Select__option, .Select-input input, .Select__input input { color:#145A91 !important; }\n      .Select-menu-outer, .Select__menu, .Select__menu-list { color:#145A91 !important; font-family:inherit !important; font-weight:400 !important; }
      .Select-option, .Select__option, .VirtualizedSelectOption { color:#145A91 !important; background:#fff !important; font-family:inherit !important; font-size:inherit !important; font-weight:400 !important; }
      .Select-option.is-focused, .Select-option:hover, .Select__option--is-focused, .Select__option:hover, .VirtualizedSelectFocusedOption { color:#145A91 !important; background:#EAF3FC !important; font-weight:800 !important; }
      .Select-option.is-selected, .Select__option--is-selected { color:#145A91 !important; font-weight:700 !important; }
      .Select-value-label, .Select__single-value, .Select-placeholder, .Select-input input, .Select__input input { font-family:inherit !important; font-weight:400 !important; color:#145A91 !important; }
      .kpi-row { gap:var(--gap) !important; margin:0 !important; }
      .kpi-card { padding:clamp(5px,.5vw,8px) !important; min-height:0 !important; }
      .kpi-card .kpi-label { font-size:clamp(9px,.8vw,12px) !important; }
      .kpi-card .kpi-value { font-size:clamp(14px,1.35vw,21px) !important; margin-top:1px !important; line-height:1.05 !important; }
      .kpi-card .kpi-note { font-size:clamp(8px,.65vw,10px) !important; margin-top:2px !important; }
      .main-row { min-height:0; height:100%; display:grid !important; grid-template-columns:minmax(0,1.05fr) minmax(0,1fr) !important; gap:var(--gap) !important; margin:0 !important; }
      .left-column { display:grid !important; grid-template-rows:minmax(0,1fr); gap:var(--gap) !important; min-height:0; min-width:0; }
      .map-card, .side-column, .detail-card, .donut-card { min-height:0 !important; min-width:0 !important; }
      .map-card { display:flex; flex-direction:column; height:100%; min-height:0; position:relative !important; }
      .panel-title { padding:clamp(5px,.6vw,9px) 10px !important; font-size:clamp(11px,.9vw,14px) !important; }
      .map-description { padding:3px 8px !important; font-size:clamp(8px,.6vw,9px) !important; }
      .map-legend { position:absolute !important; z-index:20; left:clamp(6px,.6vw,10px); bottom:clamp(6px,.6vw,10px); max-width:calc(100% - 20px); display:flex !important; flex-wrap:wrap; align-items:center; gap:5px 7px; padding:7px 9px !important; border:1px solid rgba(210,222,235,.95); border-radius:10px; background:rgba(255,255,255,.92); box-shadow:0 2px 10px rgba(18,45,80,.16); backdrop-filter:blur(4px); line-height:1.1; }
      #map { flex:1 1 0; min-height:0 !important; height:100% !important; max-height:none !important; width:100% !important; }
      #map .js-plotly-plot, #map .plot-container, #map .svg-container { width:100% !important; height:100% !important; }
      .side-column { display:grid !important; grid-template-rows:minmax(0,1.3fr) minmax(145px,.7fr); gap:var(--gap) !important; min-height:0; }
      .detail-card { display:flex; flex-direction:column; overflow:hidden; padding:0 !important; margin:0 !important; }
      #table { min-height:0; overflow:auto !important; flex:1 1 0; padding:4px !important; }
      #table > div { max-height:100% !important; }
      #province-cards { display:grid !important; grid-template-columns:repeat(3,minmax(0,1fr)) !important; grid-template-rows:minmax(0,1fr) !important; gap:var(--gap) !important; min-height:0; overflow:hidden; }
      #province-cards > div { padding:clamp(5px,.5vw,8px) !important; min-height:0; display:flex !important; flex-direction:column !important; justify-content:space-between !important; gap:2px !important; }
      #province-cards > div > div:last-child { gap:3px !important; }
      #province-cards > div > div:first-child { color:#FFFFFF !important; margin:calc(-1 * clamp(5px,.5vw,8px)) calc(-1 * clamp(5px,.5vw,8px)) 5px !important; padding:6px 8px !important; font-size:clamp(11px,.9vw,14px) !important; }
      #province-cards > div > div:nth-child(3) { font-size:clamp(20px,1.75vw,29px) !important; line-height:1.02 !important; margin:2px 0 1px !important; letter-spacing:-.25px !important; }
      #province-cards hr { margin:3px 0 !important; }
      #province-cards > div > div:last-child { gap:clamp(4px,.45vw,7px) !important; margin-top:clamp(8px,1.2vh,14px) !important; }
      #province-cards > div > div:last-child > div > div:last-child { font-size:clamp(13px,1.05vw,17px) !important; line-height:1.05 !important; }
      .dashboard-footer { font-size:clamp(8px,.65vw,10px) !important; padding:0 2px !important; line-height:1.1; }
      .dash-graph, .js-plotly-plot, .plot-container, .svg-container { max-width:100% !important; }
      @media (max-height: 800px) {
        .dashboard-shell { grid-template-rows:auto auto minmax(0,1fr) auto; }
        .dashboard-header { padding-top:5px !important; padding-bottom:5px !important; }
        #province-cards > div { padding:5px !important; }
        #province-cards > div > div:first-child { color:#FFFFFF !important; margin:-5px -5px 4px !important; padding:4px 7px !important; }
      }
      @media (max-width: 1100px) {
        .dashboard-header { grid-template-columns:minmax(72px,.18fr) minmax(160px,.65fr) minmax(520px,1.9fr); gap:8px; }
        .dashboard-header .region-title { font-size:clamp(16px,1.5vw,22px) !important; }
      }
      @media (max-width: 850px) {
        .dashboard-shell { grid-template-rows:auto auto minmax(0,1fr) auto; }
        .dashboard-header { grid-template-columns: minmax(64px,.18fr) minmax(150px,.7fr) minmax(330px,1.5fr); padding:6px 8px !important; }
        .dashboard-header .subtitle { display:none; }
        .main-row { grid-template-columns:minmax(0,1fr) !important; grid-template-rows:minmax(0,1fr) minmax(0,1fr) !important; }
        .left-column { grid-template-rows:minmax(0,1fr); }
        .side-column { grid-template-columns:minmax(0,1fr); grid-template-rows:minmax(0,1fr); }
        #province-cards { grid-template-columns:repeat(3,minmax(0,1fr)) !important; grid-template-rows:minmax(0,1fr) !important; }
      }
      @media (max-width: 560px) {
        .dashboard-shell { padding:4px; gap:4px; }
        .dashboard-header { grid-template-columns: 48px minmax(125px,.7fr) minmax(300px,1.5fr); gap:6px; }
        .filter-row { flex-wrap:nowrap !important; }
        .filter-row > div { flex:1 1 0 !important; }
        .kpi-row { display:grid !important; grid-template-columns:repeat(2,minmax(0,1fr)); }
        .main-row { grid-template-rows:minmax(0,1fr) minmax(0,1fr) !important; }
        .side-column { grid-template-columns:minmax(0,1fr); grid-template-rows:minmax(0,1fr); }
        #province-cards > div > div:nth-child(3) { font-size:12px !important; }
      }
    </style>
  </head>
  <body>
    {%app_entry%}
    <footer>
      {%config%}
      {%scripts%}
      {%renderer%}
    </footer>
  </body>
</html>"""
app.title = "EMACO2 Performance Region Kalimantan"
depo_options = [{"label":"Semua Depo","value":"ALL"}] + [{"label":x,"value":x} for x in sorted(data["DEPO"].unique())]
prov_options = [{"label":"Semua Provinsi","value":"ALL"}] + [{"label":x,"value":x} for x in PROVINSI_TARGET]

def kpi(label, value_id, note_id, icon_key):
    icon_name = ICON_ASSET_NAMES.get(icon_key)
    icon_node = (
        html.Img(
            src=app.get_asset_url(icon_name),
            alt=f"Ikon {label}",
            style={"width":"clamp(34px,3.2vw,52px)","height":"clamp(34px,3.2vw,52px)",
                   "objectFit":"contain","flexShrink":"0","marginRight":"clamp(7px,.8vw,12px)"}
        ) if icon_name else html.Div(
            {"sales":"↗","ca":"●","cr":"▣","rate":"%"}[icon_key],
            style={"width":"clamp(34px,3.2vw,52px)","height":"clamp(34px,3.2vw,52px)",
                   "display":"flex","alignItems":"center","justifyContent":"center",
                   "fontSize":"24px","fontWeight":"800","color":"#145A91","flexShrink":"0"}
        )
    )
    return card([
        html.Div([
            icon_node,
            html.Div([
                html.Div(label,className="kpi-label",style={"fontSize":"12px","fontWeight":"700","color":"#243F6B"}),
                html.Div(id=value_id,className="kpi-value",style={"fontSize":"18px","fontWeight":"800","color":"#09285C","marginTop":"2px"}),
                html.Div(id=note_id,className="kpi-note",style={"fontSize":"10px","marginTop":"2px"})
            ],style={"minWidth":"0","flex":"1"})
        ],style={"display":"flex","alignItems":"center","height":"100%","minWidth":"0"})
    ], {"flex":"1 1 0","minWidth":"0","minHeight":"0"},className="kpi-card")

app.layout = html.Div([
    html.Div([
        html.Div(
            html.Img(
                src=app.get_asset_url(LOGO_ASSET_NAME),
                alt="SNS Group Logo",
                style={
                    "display":"block", "maxWidth":"100%", "maxHeight":"72px",
                    "width":"100%", "height":"auto", "objectFit":"contain",
                    "objectPosition":"left center", "margin":"0"
                }
            ),
            className="header-logo-space",
            style={"display":"flex","alignItems":"center","justifyContent":"flex-start","minWidth":"0"}
        ),
        html.Div([
            html.Div(f"{SKU_DEFAULT} PERFORMANCE",id="sku-heading",className="eyebrow",style={"fontSize":"22px","fontWeight":"900"}),
            html.Div(["REGION ",html.Span("KALIMANTAN",style={"color":"#FFD84D"})],
                     className="region-title",style={"fontSize":"32px","fontWeight":"900","lineHeight":"1.0"}),
            html.Div("MTD • VS LAST YEAR • VS AVG L3M • VS LAST MONTH • CUSTOMER ACTIVE",
                     className="subtitle",style={"fontSize":"11px","fontWeight":"400","marginTop":"4px","whiteSpace":"nowrap","letterSpacing":"0"})
        ],className="header-title-block"),
        card([html.Div("FILTER DASHBOARD",className="filter-title",style={"fontWeight":"800","marginBottom":"4px"}),
            html.Div([
                html.Div([html.Label("SKU"),dcc.Dropdown(id="sku",options=[{"label":x,"value":x} for x in DATA_BY_SKU],value=SKU_DEFAULT,clearable=False)],
                         style={"flex":"1 1 0","minWidth":"0"}),
                html.Div([html.Label("Depo"),dcc.Dropdown(id="depo",options=depo_options,value="ALL",clearable=False)],
                         style={"flex":"1 1 0","minWidth":"0"}),
                html.Div([html.Label("Provinsi"),dcc.Dropdown(id="prov",options=prov_options,value="ALL",clearable=False)],
                         style={"flex":"1 1 0","minWidth":"0"}),
                html.Div([html.Label("Kabupaten/Kota"),dcc.Dropdown(id="kab",options=[{"label":"Semua Kabupaten","value":"ALL"}],value="ALL",clearable=False)],
                         style={"flex":"1 1 0","minWidth":"0"})
            ],className="filter-row",style={"display":"flex","gap":"6px","flexWrap":"nowrap"})],
            {"marginBottom":"0"},className="header-filter")
    ],className="dashboard-header",style={"background":"linear-gradient(100deg,#09295A,#145A91)","color":"white",
             "padding":"12px 20px","borderRadius":"0 0 12px 12px"}),
    html.Div([kpi("Total Sales ACT MTD","sales","salesnote","sales"),kpi("CA","active","activenote","ca"),
              kpi("CR","registered","registerednote","cr"),kpi("Active Rate","rate","ratenote","rate")],
             className="kpi-row",style={"display":"flex","gap":"8px","flexWrap":"nowrap","marginBottom":"0"}),
    html.Div([
        html.Div([
            card([panel_title("Peta Kinerja Sales Region Kalimantan"),
                  html.Div("Heatmap ACT MTD per kabupaten • semakin gelap = ACT MTD relatif semakin tinggi",
                           className="map-description",style={"padding":"4px 9px","fontSize":"10px","color":"#536984"}),
                  dcc.Graph(id="map",config={"responsive":True},style={"height":"100%", "minHeight":"0", "width":"100%"}),
                  html.Div(id="map-legend",className="map-legend",style={})],
                 {"padding":"0","overflow":"hidden"},className="map-card"),
        ], className="left-column"),
        html.Div([
            card([panel_title("Detail Kinerja per Kabupaten/Kota"),html.Div(id="table",style={"padding":"7px","overflowX":"auto"})],
                 {"padding":"0","overflow":"hidden","marginBottom":"0"},className="detail-card"),
            html.Div(id="province-cards",style={"display":"grid","gridTemplateColumns":"repeat(3,minmax(0,1fr))","gap":"8px"})
        ],className="side-column",style={"flex":"1","minWidth":"0","width":"100%"})
    ],className="main-row",style={"display":"grid","gridTemplateColumns":"minmax(0,1.05fr) minmax(0,1fr)","alignItems":"stretch","gap":"8px","marginBottom":"0","width":"100%","minWidth":"0"}),
    html.Div("Sumber: file Excel SKU terpilih dan GeoJSON kabupaten. Semua angka mengikuti filter aktif.",
             className="dashboard-footer",style={"fontSize":"10px","color":"#63758B","padding":"0 2px"})
],className="dashboard-shell",style={"background":"#F3F7FB","padding":"8px","fontFamily":"Arial,sans-serif","color":"#102C58","width":"100%","maxWidth":"100vw","boxSizing":"border-box","overflow":"hidden"})

# Daftar depo mengikuti SKU yang sedang dipilih.
@app.callback(Output("depo", "options"), Output("depo", "value"), Output("sku-heading", "children"), Input("sku", "value"))
def options_depo(sku):
    sku_data = DATA_BY_SKU.get(sku, data)
    opts = [{"label": "Semua Depo", "value": "ALL"}] + [
        {"label": x, "value": x} for x in sorted(sku_data["DEPO"].dropna().unique())
    ]
    return opts, "ALL", f"{sku} PERFORMANCE"

# Dropdown provinsi menyesuaikan depo; pilihan yang tidak valid di-reset ke Semua.
@app.callback(Output("prov","options"),Output("prov","value"),Input("sku","value"),Input("depo","value"),Input("prov","value"))
def options_prov(sku, depo, current):
    sku_data = AGG_BY_SKU.get(sku, AGG_BY_SKU[SKU_DEFAULT])
    d = sku_data if depo == "ALL" else sku_data[sku_data["DEPO"] == depo]
    available=[p for p in PROVINSI_TARGET if normalisasi(p) in set(d["provinsi_key"])]
    opts=[{"label":"Semua Provinsi","value":"ALL"}]+[{"label":p,"value":p} for p in available]
    if current not in ["ALL"]+available: current="ALL"
    return opts,current

@app.callback(Output("kab","options"),Output("kab","value"),Input("sku","value"),Input("depo","value"),Input("prov","value"),Input("kab","value"))
def options_kab(sku,depo,prov,current):
    d = AGG_BY_SKU.get(sku, AGG_BY_SKU[SKU_DEFAULT])
    if depo != "ALL":
        d = d[d["DEPO"] == depo]
    if prov != "ALL":
        d = d[d["provinsi_key"] == normalisasi(prov)]
    # MultiIndex membership menggantikan gdf.apply(row-by-row).
    keys = pd.MultiIndex.from_frame(d[["provinsi_key", "kabupaten_key"]].drop_duplicates())
    geo_keys = pd.MultiIndex.from_arrays([gdf["provinsi_key"], gdf["kabupaten_key"]])
    matches = gdf.loc[geo_keys.isin(keys), ["provinsi_key", "kabupaten_key", "kabupaten_geo", "provinsi"]]
    matches = matches.sort_values("kabupaten_geo").drop_duplicates(["provinsi_key", "kabupaten_key"])
    opts = [{"label":"Semua Kabupaten", "value":"ALL"}]
    opts.extend({"label":f'{r.kabupaten_geo} — {r.provinsi}',
                 "value":r.provinsi_key + "||" + r.kabupaten_key}
                for r in matches.itertuples(index=False))
    valid_values = {o["value"] for o in opts}
    if current not in valid_values:
        current = "ALL"
    return opts, current

@app.callback(
    Output("sales","children"),Output("salesnote","children"),
    Output("active","children"),Output("activenote","children"),
    Output("registered","children"),Output("registerednote","children"),
    Output("rate","children"),Output("ratenote","children"),
    Output("map","figure"),Output("map-legend","children"),
    Output("table","children"),Output("province-cards","children"),
    Input("sku","value"),Input("depo","value"),Input("prov","value"),Input("kab","value"))
def update(sku,depo,prov,kab):
    sku_data = AGG_BY_SKU.get(sku, AGG_BY_SKU[SKU_DEFAULT])
    d = sku_data
    if depo!="ALL": d=d[d["DEPO"]==depo]
    if prov!="ALL": d=d[d["provinsi_key"]==normalisasi(prov)]
    if kab!="ALL":
        pk,kk=kab.split("||",1)
        d=d[(d["provinsi_key"]==pk)&(d["kabupaten_key"]==kk)]

    sales=d["ACT MTD"].sum(); ly=d["LY"].sum(); l3m=d["AVG L3M"].sum(); lm=d["LM"].sum()
    active=d["CUST ACT"].sum(); registered=d["CUST REG"].sum()
    rate=100*active/registered if registered else 0
    gl, g3, gm=growth(sales,ly),growth(sales,l3m),growth(sales,lm)
    def note_growth(a,b,c):
        return html.Div([
            html.Span("vs LY "+pct(a),style={"color":HIJAU if pd.notna(a) and a>=0 else MERAH,"marginRight":"8px"}),
            html.Span("vs Avg L3M "+pct(b),style={"color":HIJAU if pd.notna(b) and b>=0 else MERAH,"marginRight":"8px"}),
            html.Span("vs LM "+pct(c),style={"color":HIJAU if pd.notna(c) and c>=0 else MERAH})
        ])

    # Susun metrik berdasarkan key kabupaten; geometri dan GeoJSON tetap di cache.
    rec = d.groupby(["provinsi_key", "kabupaten_key"], as_index=False).agg(
        **{"ACT MTD":("ACT MTD","sum"), "LY":("LY","sum"),
           "AVG L3M":("AVG L3M","sum"), "LM":("LM","sum"),
           "CUST ACT":("CUST ACT","sum"), "CUST REG":("CUST REG","sum")})
    metric_cols = ["ACT MTD", "LY", "AVG L3M", "LM", "CUST ACT", "CUST REG"]
    metric_lookup = rec.set_index(["provinsi_key", "kabupaten_key"])[metric_cols]
    geo_keys = pd.MultiIndex.from_arrays([gdf["provinsi_key"], gdf["kabupaten_key"]])
    all_values = metric_lookup.reindex(geo_keys).fillna(0).reset_index(drop=True)
    values = all_values
    province_max = {
        p: float(all_values.loc[gdf["provinsi"].eq(p).to_numpy(), "ACT MTD"].max())
        for p in PROVINSI_TARGET
    }
    gmapp = gdf.copy()  # hanya tabel geometri berukuran kabupaten, bukan 15 ribu baris Excel
    if prov != "ALL":
        mask = gmapp["provinsi"] == prov
        gmapp = gmapp.loc[mask]
        values = values.loc[mask.to_numpy()]
    if kab != "ALL":
        pk, kk = kab.split("||", 1)
        mask = (gmapp["provinsi_key"] == pk) & (gmapp["kabupaten_key"] == kk)
        gmapp = gmapp.loc[mask]
        values = values.loc[mask.to_numpy()]
    gmapp = gmapp.reset_index(drop=True)
    values = values.reset_index(drop=True)
    # Satu Choroplethmap trace untuk seluruh kabupaten; garis batas bawaan Plotly.
    # Intensitas dinormalisasi di dalam tiap provinsi dan tiap provinsi mempertahankan paletnya.
    z_values = []
    for row_idx, row in gmapp.iterrows():
        prov_name = row["provinsi"]
        maxval = province_max.get(prov_name, 0.0)
        intensity = float(values.iloc[row_idx]["ACT MTD"]) / maxval if maxval > 0 else 0.0
        segment = {"Kalimantan Tengah":0, "Kalimantan Selatan":1, "Kalimantan Timur":2}[prov_name]
        z_values.append((segment + intensity) / 3.0)
    colorscale = []
    for i, p in enumerate(PROVINSI_TARGET):
        for stop, color in WARNA_PROVINSI[p]:
            colorscale.append([((i + stop) / 3.0), color])
    customdata = [[gmapp.iloc[i]["kabupaten_geo"], gmapp.iloc[i]["provinsi"],
                   values.iloc[i]["ACT MTD"], values.iloc[i]["CUST ACT"], values.iloc[i]["CUST REG"]]
                  for i in range(len(gmapp))]
    fig = go.Figure()
    fig.add_trace(go.Choroplethmap(
        geojson=GEOJSON_CACHE, featureidkey="properties.feature_id",
        locations=gmapp["feature_id"].astype(str), z=z_values, zmin=0, zmax=1,
        colorscale=colorscale, marker_opacity=.9,
        marker_line_color="white", marker_line_width=.8,
        customdata=customdata,
        hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<br>ACT MTD: Rp %{customdata[2]:,.0f}<br>Cust Active: %{customdata[3]:,.0f}<br>Cust Registered: %{customdata[4]:,.0f}<extra></extra>",
        showscale=False, name="ACT MTD"))
    # Fokus peta khusus Kalimantan Timur, Tengah, dan Selatan.
    # Saat semua provinsi dipilih, gunakan pusat Kalimantan bagian selatan-timur dan zoom lebih dekat.
    if not gmapp.empty:
        minx,miny,maxx,maxy=gmapp.total_bounds
        bounds_center={"lat":(miny+maxy)/2,"lon":(minx+maxx)/2}
        if prov == "ALL" and kab == "ALL":
            center={"lat":-1.45,"lon":115.05}
            zoom=5.15
        elif kab != "ALL":
            center=bounds_center
            zoom=7.0
        else:
            center=bounds_center
            zoom=6.0
    else:
        center={"lat":-1.45,"lon":115.05}
        zoom=5.15
    fig.update_layout(map={"style":"carto-positron","center":center,"zoom":zoom},
        margin={"l":0,"r":0,"t":0,"b":0},paper_bgcolor="white")
    legend=[]
    for p in PROVINSI_TARGET:
        if prov!="ALL" and p!=prov: continue
        legend.append(html.Span([
            html.Span(style={"display":"inline-block","width":"9px","height":"9px","borderRadius":"50%","backgroundColor":WARNA_SOLID[p],"boxShadow":"0 0 0 3px "+WARNA_SOLID[p]+"22","marginRight":"7px","flexShrink":"0"}),
            html.Span(p,style={"fontSize":"clamp(9px,.65vw,11px)","fontWeight":"700","color":"#18395F","whiteSpace":"nowrap"}),
            html.Span("rendah → tinggi",style={"fontSize":"clamp(8px,.58vw,10px)","color":"#667991","marginLeft":"5px","whiteSpace":"nowrap"})
        ],style={"display":"inline-flex","alignItems":"center","padding":"4px 7px","borderRadius":"7px","background":"#F7FAFD","border":"1px solid #E4EBF3"}))

    table=make_table(d)
    cards=[]
    for p in PROVINSI_TARGET:
        sub=d[d["provinsi_key"]==normalisasi(p)]
        if sub.empty: continue
        s=sub["ACT MTD"].sum(); lp=sub["LY"].sum(); l3=sub["AVG L3M"].sum(); mp=sub["LM"].sum()
        ca=sub["CUST ACT"].sum(); reg=sub["CUST REG"].sum(); cr=100*ca/reg if reg else 0
        cards.append(card([
            html.Div(p,style={"background":WARNA_SOLID[p],"color":"#FFFFFF","fontWeight":"800","padding":"5px 8px","margin":"-6px -6px 5px"}),
            html.Div("Sales ACT MTD",style={"fontSize":"11px","color":"#64758B"}),
            html.Div(rupiah(s),style={"fontSize":"18px","fontWeight":"800","color":"#09285C"}),
            html.Div([
                html.Span("vs LY "+pct(growth(s,lp)),style={"color":HIJAU if s>=lp else MERAH,"marginRight":"10px"}),
                html.Span("vs L3M "+pct(growth(s,l3)),style={"color":HIJAU if s>=l3 else MERAH,"marginRight":"10px"}),
                html.Span("vs LM "+pct(growth(s,mp)),style={"color":HIJAU if s>=mp else MERAH})
            ],style={"fontSize":"10px","fontWeight":"700","marginTop":"4px"}),
            html.Hr(style={"border":"0","borderTop":"1px solid #E5EDF5"}),
            html.Div([
                html.Div([html.Div("CA",style={"fontSize":"11px"}),html.Div(angka(ca),style={"fontSize":"16px","fontWeight":"800"})],style={"flex":"1"}),
                html.Div([html.Div("CR",style={"fontSize":"11px"}),html.Div(angka(reg),style={"fontSize":"16px","fontWeight":"800"})],style={"flex":"1"}),
                html.Div([html.Div("%CA",style={"fontSize":"11px"}),html.Div(f"{cr:.1f}%",style={"fontSize":"16px","fontWeight":"800"})],style={"flex":".7"})
            ],style={"display":"flex","gap":"8px"})
        ]))
    return (rupiah(sales),note_growth(gl,g3,gm),angka(active),html.Span(f"{rate:.1f}% dari {angka(registered)} registered"),
            angka(registered),html.Span("Customer registered pada filter aktif"),
            f"{rate:.1f}%",html.Span("vs LY "+pct(gl),style={"color":HIJAU if pd.notna(gl) and gl>=0 else MERAH}),
            fig,legend,table,cards)

# Jalankan lokal di VS Code/terminal.
if __name__ == "__main__":
    print("\\nDashboard berjalan di http://127.0.0.1:8050")
    print("Tekan Ctrl+C di terminal untuk menghentikan dashboard.")
    app.run(debug=False, port=8050)
