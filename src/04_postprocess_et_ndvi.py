import argparse, csv, os, re, sys
from datetime import datetime
from pathlib import Path

ENV_BIN = Path(sys.prefix) / "Library" / "bin"
if os.name == "nt" and ENV_BIN.exists():
    os.environ["PATH"] = f"{ENV_BIN};{os.environ.get('PATH', '')}"
    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(str(ENV_BIN))

import numpy as np, yaml
from osgeo import gdal

gdal.UseExceptions()
DATE_PATTERN = re.compile(r"(\d{4})[_-](\d{2})[_-](\d{2})")
DEFAULT_SEASONS = {"DJF": [12, 1, 2], "MAM": [3, 4, 5], "JJA": [6, 7, 8], "SON": [9, 10, 11]}

def load_config(p: Path) -> dict:
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {} if p.exists() else {}

def read_geotiff(tif_path: Path):
    ds = gdal.Open(str(tif_path), gdal.GA_ReadOnly)
    if ds is None:
        raise RuntimeError(f"Could not open raster: {tif_path}")
    b = ds.GetRasterBand(1)
    nd = b.GetNoDataValue()
    arr = b.ReadAsArray().astype(np.float32)
    bad = ~np.isfinite(arr) | (np.isclose(arr, float(nd)) if nd is not None else False)
    arr[bad] = np.nan
    meta = {"width": ds.RasterXSize, "height": ds.RasterYSize, "transform": ds.GetGeoTransform(), "projection": ds.GetProjection()}
    ds = None
    return arr, meta

def write_geotiff(out_path: Path, arr: np.ndarray, meta: dict, nodata: float = -9999.0):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ds = gdal.GetDriverByName("GTiff").Create(str(out_path), meta["width"], meta["height"], 1, gdal.GDT_Float32, options=["COMPRESS=LZW", "TILED=YES"])
    ds.SetGeoTransform(meta["transform"])
    if meta["projection"]:
        ds.SetProjection(meta["projection"])
    band = ds.GetRasterBand(1)
    band.WriteArray(np.where(np.isfinite(arr), arr, nodata).astype(np.float32))
    band.SetNoDataValue(float(nodata))
    band.FlushCache()
    ds = None

def spatial_gap_fill(arr: np.ndarray, radius: int = 2) -> np.ndarray:
    out = arr.copy()
    nans = np.argwhere(np.isnan(out))
    if nans.size == 0 or np.all(np.isnan(out)):
        return out
    r_max, c_max = out.shape
    for r, c in nans:
        vals = out[max(0, r - radius):min(r_max, r + radius + 1), max(0, c - radius):min(c_max, c + radius + 1)]
        ok = vals[np.isfinite(vals)]
        if ok.size:
            out[r, c] = float(np.mean(ok))
    return out

def temporal_gap_fill(stack: np.ndarray, dates: list[datetime]) -> np.ndarray:
    out = stack.copy()
    if out.shape[0] < 2:
        return out
    t = np.array([(d - dates[0]).total_seconds() / 86400.0 for d in dates], dtype=np.float64)
    counts = np.sum(np.isfinite(out), axis=0)
    for r, c in np.argwhere(counts >= 2):
        s = out[:, r, c]
        if not np.all(np.isfinite(s)):
            ok = np.isfinite(s)
            out[:, r, c] = np.interp(t, t[ok], s[ok]).astype(np.float32)
    return out

def discover_rasters(root: Path, kw: str) -> list[tuple[datetime, Path]]:
    found = []
    if not root.exists():
        return found
    for p in sorted(root.rglob("*.tif")):
        if kw.lower() in p.name.lower():
            m = DATE_PATTERN.search(p.stem)
            if m:
                found.append((datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))), p))
    return sorted(found, key=lambda x: x[0])

def add_stat(rows: list, var: str, scale: str, period: str, arr: np.ndarray, p: Path):
    ok = arr[np.isfinite(arr)]
    if ok.size == 0:
        rows.append([var, scale, period, "nan", "nan", "nan", str(p)])
    else:
        rows.append([var, scale, period, f"{float(np.min(ok)):.4f}", f"{float(np.mean(ok)):.4f}", f"{float(np.max(ok)):.4f}", str(p)])

def process_var(var: str, kw: str, root: Path, out_root: Path, seasons: dict, rows: list):
    items = discover_rasters(root, kw)
    if not items:
        print(f"[{var}] No rasters found for '{kw}'")
        return
    meta, valid = None, []
    for dt, p in items:
        arr, m = read_geotiff(p)
        if meta is None:
            meta = m
        elif (m["width"], m["height"]) != (meta["width"], meta["height"]):
            continue
        valid.append((dt, arr))
    if not valid:
        return
    dates = [d for d, _ in valid]
    stack = temporal_gap_fill(np.stack([a for _, a in valid], axis=0), dates)
    for i in range(stack.shape[0]):
        stack[i] = spatial_gap_fill(stack[i], radius=2)
    vdir = out_root / var.lower()
    monthly = {}
    for yr, mo in sorted({(d.year, d.month) for d in dates}):
        idxs = [i for i, d in enumerate(dates) if (d.year, d.month) == (yr, mo)]
        m_arr = spatial_gap_fill(np.nanmean(stack[idxs], axis=0), radius=3)
        monthly[(yr, mo)] = m_arr
        out_p = vdir / f"{var}_monthly_{yr}_{mo:02d}.tif"
        write_geotiff(out_p, m_arr, meta)
        add_stat(rows, var, "monthly", f"{yr}-{mo:02d}", m_arr, out_p)
    for yr in sorted({d.year for d in dates}):
        for sname, mos in seasons.items():
            s_list = [monthly[(y, m)] for (y, m) in monthly if y == yr and m in mos]
            if s_list:
                s_arr = np.nanmean(np.stack(s_list, axis=0), axis=0)
                out_p = vdir / f"{var}_seasonal_{yr}_{sname}.tif"
                write_geotiff(out_p, s_arr, meta)
                add_stat(rows, var, "seasonal", f"{yr}-{sname}", s_arr, out_p)
        y_idxs = [i for i, d in enumerate(dates) if d.year == yr]
        ann_m = np.nanmean(stack[y_idxs], axis=0)
        out_p = vdir / f"{var}_annual_mean_{yr}.tif"
        write_geotiff(out_p, ann_m, meta)
        add_stat(rows, var, "annual_mean", str(yr), ann_m, out_p)
        if "et" in var.lower():
            est = ann_m * 365.0
            est_p = vdir / f"{var}_annual_est_mm_{yr}.tif"
            write_geotiff(est_p, est, meta)
            add_stat(rows, var, "annual_est_365d", str(yr), est, est_p)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/config.yaml")
    cfg = load_config(Path(ap.parse_args().config))
    out_base = Path(cfg.get("paths", {}).get("outputs", "data/outputs"))
    pcfg = cfg.get("postprocessing", {})
    search_root = Path(pcfg.get("input_dir", out_base))
    out_root = Path(pcfg.get("output_dir", out_base / "postprocessed"))
    seasons = pcfg.get("seasons", DEFAULT_SEASONS)
    rows = []
    process_var("ETact_24", "ETact_24", search_root, out_root, seasons, rows)
    process_var("NDVI", "NDVI", search_root, out_root, seasons, rows)
    out_root.mkdir(parents=True, exist_ok=True)
    csv_p = out_root / "postprocessing_summary.csv"
    with open(csv_p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["variable", "scale", "period", "min", "mean", "max", "output_file"])
        w.writerows(rows)
    print(f"Saved summary: {csv_p}")
    for r in rows:
        print(f"  {r[0]} | {r[1]} | {r[2]} -> min={r[3]}, mean={r[4]}, max={r[5]}")

if __name__ == "__main__":
    main()
