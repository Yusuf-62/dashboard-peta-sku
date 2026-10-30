"""Ekspor data Excel, GeoJSON, dan gambar aset ke JSON untuk GitHub Pages.

Folder yang dibaca (berada satu tingkat di atas folder scripts):
  Data SKU/Chocolatos/Seri 5/   Excel per SKU (.xlsx/.xls)
  Data SKU/Chocolatos/Seri 8/   Excel per SKU (.xlsx/.xls)
  Data SKU/Malkist/Seri 2/      Excel per SKU (.xlsx/.xls)
  Data SKU/Malkist/Seri 8/      Excel per SKU (.xlsx/.xls)
  Kab yang digunakan/ GeoJSON kabupaten, di dalam subfolder kaltim/kalteng/kalsel
  Assets/images/      gambar PNG/JPG/JPEG/WebP (opsional)

Output:
  data/dashboard.json  data agregat per SKU, depo, provinsi, kabupaten
  data/geojson.json    FeatureCollection batas kabupaten/kota\n  data/kecamatan_geojson.json  FeatureCollection batas kecamatan (dipakai saat kabupaten dipilih)
  data/assets.json     manifest gambar berformat data URI/base64
"""
from pathlib import Path
import base64
import json
import mimetypes
import re
import unicodedata
from datetime import datetime, timezone

import pandas as pd
import geopandas as gpd

PROJECT_DIR = Path(__file__).resolve().parents[1]
EXCEL_DIR = PROJECT_DIR / "Data SKU"
GEO_DIR = PROJECT_DIR / "Kab yang digunakan"
ASSETS_DIR = PROJECT_DIR / "Assets" / "images"
OUTPUT_DIR = PROJECT_DIR / "data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PROVINCES = {
    "kaltim": "Kalimantan Timur",
    "kalteng": "Kalimantan Tengah",
    "kalsel": "Kalimantan Selatan",
}
ALIASES = {
    "kaltim": ["KALTIM", "KALIMANTANTIMUR"],
    "kalteng": ["KALTENG", "KALIMANTANTENGAH"],
    "kalsel": ["KALSEL", "KALIMANTANSELATAN"],
}
REQUIRED = ["DEPO", "PROVINSI", "KABUPATEN", "ACT MTD", "LY", "AVG L3M", "LM", "CUST ACT", "CUST REG", "Id Pelanggan"]
NUMERIC = ["ACT MTD", "LY", "AVG L3M", "LM", "CUST ACT", "CUST REG"]


def normalize(value):
    if pd.isna(value):
        return ""
    value = unicodedata.normalize("NFKD", str(value))
    value = "".join(ch for ch in value if not unicodedata.combining(ch)).upper().strip()
    value = re.sub(r"^(KABUPATEN|KAB\.|KOTA ADMINISTRASI|KOTA)\s+", "", value)
    return re.sub(r"[^A-Z0-9]", "", value)


def province_for_path(path):
    parts = [normalize(part) for part in path.parts]
    for key, aliases in ALIASES.items():
        if any(alias in part for alias in aliases for part in parts):
            return key
    return None


def load_excel(path):
    frame = pd.read_excel(path)
    frame.columns = [str(col).strip() for col in frame.columns]
    missing = [col for col in REQUIRED if col not in frame.columns]
    if missing:
        raise ValueError(f"Kolom wajib tidak ditemukan: {missing}")
    for col in NUMERIC:
        frame[col] = pd.to_numeric(frame[col].astype(str).str.replace(",", ".", regex=False), errors="coerce").fillna(0)
    frame["DEPO"] = frame["DEPO"].fillna("(DEPO KOSONG)").astype(str).str.strip()
    frame["PROVINSI"] = frame["PROVINSI"].fillna("").astype(str).str.strip()
    frame["KABUPATEN"] = frame["KABUPATEN"].fillna("").astype(str).str.strip()
    kec_col = next((c for c in frame.columns if normalize(c) in {"KECAMATAN", "NAMAKECAMATAN", "KECAMATANNAME"}), None)
    if kec_col is not None:
        frame["KECAMATAN"] = frame[kec_col].fillna("").astype(str).str.strip()
    else:
        frame["KECAMATAN"] = ""
    frame["provinsi_key"] = frame["PROVINSI"].map(normalize)
    frame["kabupaten_key"] = frame["KABUPATEN"].map(normalize)
    target = {normalize(name) for name in PROVINCES.values()}
    frame = frame[frame["provinsi_key"].isin(target) & frame["kabupaten_key"].ne("")].copy()
    # Struktur folder menjadi hierarki menu SKU.
    # Contoh: Chocolatos/Seri 5/CWSCO4.xlsx -> Chocolatos/Seri 5/CWSCO4.
    # File yang masih langsung di folder Data SKU tetap memakai nama file.
    relative = path.relative_to(EXCEL_DIR)
    parts = list(relative.with_suffix("").parts)
    parts[-1] = re.sub(r"^SKU\\s+", "", parts[-1].strip(), flags=re.IGNORECASE).strip() or parts[-1]
    sku = "/".join(parts)
    group_cols = ["DEPO", "PROVINSI", "provinsi_key", "KABUPATEN", "kabupaten_key"]
    if frame["KECAMATAN"].astype(str).str.strip().ne("").any():
        group_cols.append("KECAMATAN")
    grouped = frame.groupby(group_cols, as_index=False, sort=False, dropna=False).agg({
        "ACT MTD": "sum", "LY": "sum", "AVG L3M": "sum", "LM": "sum", "CUST ACT": "sum", "CUST REG": "sum"
    })
    grouped.insert(0, "sku", sku)
    return grouped


def export_dashboard_data():
    if not EXCEL_DIR.is_dir():
        raise FileNotFoundError(f"Folder Excel tidak ditemukan: {EXCEL_DIR}")
    files = sorted([*EXCEL_DIR.rglob("*.xlsx"), *EXCEL_DIR.rglob("*.xls")])
    files = [p for p in files if not p.name.startswith("~$")]
    if not files:
        raise FileNotFoundError(f"Tidak ditemukan file Excel di {EXCEL_DIR}")
    frames = []
    for path in files:
        try:
            frame = load_excel(path)
            if frame.empty:
                print(f"Peringatan: tidak ada baris wilayah target pada {path.name}")
            frames.append(frame)
            print(f"Excel diproses: {path.relative_to(EXCEL_DIR)} ({len(frame):,} baris agregat)")
        except Exception as exc:
            print(f"SKU dilewati ({path.name}): {exc}")
    frames = [f for f in frames if not f.empty]
    if not frames:
        raise ValueError("Tidak ada Excel SKU yang berhasil diproses. Periksa nama kolom dan data.")
    combined = pd.concat(frames, ignore_index=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "skus": sorted(combined["sku"].unique().tolist()),
        "records": combined.to_dict(orient="records"),
    }
    (OUTPUT_DIR / "dashboard.json").write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    print(f"JSON data ditulis: {OUTPUT_DIR / 'dashboard.json'} ({len(combined):,} baris)")


def export_geojson():
    """Ekspor batas kabupaten dan kecamatan secara terpisah.

    Struktur yang didukung:
      Kab yang digunakan/kaltim/*.geojson
      Kab yang digunakan/kalsel/*.geojson
      Kab yang digunakan/kalteng/*.geojson
      Kab yang digunakan/Kecamatan/kaltim/*.geojson
      Kab yang digunakan/Kecamatan/kalsel/*.geojson
      Kab yang digunakan/Kecamatan/kalteng/*.geojson
    """
    if not GEO_DIR.is_dir():
        raise FileNotFoundError(f"Folder GeoJSON tidak ditemukan: {GEO_DIR}")

    candidates = sorted(p for p in GEO_DIR.rglob("*") if p.is_file() and p.suffix.lower() in {".geojson", ".json"})
    kec_candidates = [p for p in candidates if any(normalize(part) == "KECAMATAN" for part in p.relative_to(GEO_DIR).parts[:-1])]
    kab_candidates = [p for p in candidates if p not in kec_candidates]

    def export_level(paths, level):
        items = [(path, province_for_path(path.relative_to(GEO_DIR))) for path in paths]
        items = [(path, key) for path, key in items if key]
        frames = []
        for path, key in items:
            try:
                gdf = gpd.read_file(path)
                if gdf.empty:
                    continue
                gdf["provinsi"] = PROVINCES[key]
                gdf["sumber_file"] = path.stem
                if gdf.crs is None:
                    gdf = gdf.set_crs("EPSG:4326")
                elif gdf.crs.to_epsg() != 4326:
                    gdf = gdf.to_crs("EPSG:4326")
                frames.append(gdf)
            except Exception as exc:
                print(f"GeoJSON {level} dilewati ({path.name}): {exc}")
        if not frames:
            if level == "kecamatan":
                print("Info: GeoJSON kecamatan belum tersedia; data kabupaten tetap diekspor.")
                return {"type": "FeatureCollection", "features": []}
            raise FileNotFoundError("GeoJSON kabupaten tidak ditemukan di subfolder kaltim/kalteng/kalsel.")

        merged = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), geometry="geometry", crs="EPSG:4326")
        if level == "kabupaten":
            name_candidates = ["WADMKK", "KABUPATEN", "kabupaten", "NAMOBJ", "name", "NAME_2", "shapeName"]
            name_col = next((col for col in name_candidates if col in merged.columns), None)
            merged["kabupaten_geo"] = merged[name_col].astype(str) if name_col else merged["sumber_file"].astype(str)
        else:
            kec_candidates_names = ["WADMKC", "KECAMATAN", "kecamatan", "NAMOBJ", "name", "NAME_3", "shapeName"]
            kec_col = next((col for col in kec_candidates_names if col in merged.columns), None)
            kab_candidates_names = ["WADMKK", "KABUPATEN", "kabupaten", "WADMKK", "NAME_2"]
            kab_col = next((col for col in kab_candidates_names if col in merged.columns), None)
            merged["kecamatan_geo"] = merged[kec_col].astype(str) if kec_col else merged["sumber_file"].astype(str)
            merged["kabupaten_geo"] = merged[kab_col].astype(str) if kab_col else ""

        merged["provinsi_key"] = merged["provinsi"].map(normalize)
        merged["kabupaten_key"] = merged["kabupaten_geo"].map(normalize)
        if level == "kecamatan":
            merged["kecamatan_key"] = merged["kecamatan_geo"].map(normalize)
        merged = merged[merged["provinsi_key"].isin({normalize(x) for x in PROVINCES.values()})].reset_index(drop=True)
        features = []
        for idx, row in merged.iterrows():
            geometry = row.geometry
            if geometry is None or geometry.is_empty:
                continue
            props = {
                "feature_id": str(idx), "kabupaten_geo": str(row["kabupaten_geo"]),
                "provinsi": str(row["provinsi"]), "provinsi_key": str(row["provinsi_key"]),
                "kabupaten_key": str(row["kabupaten_key"]),
            }
            if level == "kecamatan":
                props["kecamatan_geo"] = str(row["kecamatan_geo"])
                props["kecamatan_key"] = str(row["kecamatan_key"])
            features.append({"type": "Feature", "id": str(idx), "properties": props, "geometry": geometry.__geo_interface__})
        return {"type": "FeatureCollection", "features": features}

    kab_collection = export_level(kab_candidates, "kabupaten")
    kec_collection = export_level(kec_candidates, "kecamatan")
    (OUTPUT_DIR / "geojson.json").write_text(json.dumps(kab_collection, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    (OUTPUT_DIR / "kecamatan_geojson.json").write_text(json.dumps(kec_collection, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    print(f"GeoJSON kabupaten ditulis: {OUTPUT_DIR / 'geojson.json'} ({len(kab_collection['features'])} fitur)")
    print(f"GeoJSON kecamatan ditulis: {OUTPUT_DIR / 'kecamatan_geojson.json'} ({len(kec_collection['features'])} fitur)")


def export_assets_manifest():
    manifest = {}
    if ASSETS_DIR.is_dir():
        for path in sorted(ASSETS_DIR.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
                continue
            mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            manifest[path.name] = f"data:{mime};base64,{encoded}"
    out = OUTPUT_DIR / "assets.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    print(f"Manifest aset ditulis: {out} ({len(manifest)} gambar)")


if __name__ == "__main__":
    export_dashboard_data()
    export_geojson()
    export_assets_manifest()
    print("Selesai. Periksa folder data/, lalu git add, commit, dan push.")
