import argparse
import glob
import os
import sys
from pathlib import Path

ENV_BIN = Path(sys.prefix) / "Library" / "bin"
if os.name == "nt" and ENV_BIN.exists():
    os.environ["PATH"] = f"{ENV_BIN};{os.environ.get('PATH', '')}"
    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(str(ENV_BIN))

import yaml
from osgeo import gdal

gdal.UseExceptions()


def warp_to_reference(src_path: Path, dst_path: Path, ref_ds) -> None:
    gt = ref_ds.GetGeoTransform()
    x_res = abs(gt[1])
    y_res = abs(gt[5])
    dst_srs = ref_ds.GetProjection()

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    opts = gdal.WarpOptions(
        dstSRS=dst_srs,
        xRes=x_res,
        yRes=y_res,
        targetAlignedPixels=True,
        resampleAlg=gdal.GRA_Bilinear,
        dstNodata=-9999.0,
        multithread=True,
    )
    out = gdal.Warp(str(dst_path), str(src_path), options=opts)
    if out is None:
        raise RuntimeError(f"Failed to warp {src_path} -> {dst_path}")
    out.FlushCache()
    out = None


def main() -> None:
    ap = argparse.ArgumentParser(description="Align GLDAS meteo and soil rasters to a reference grid.")
    ap.add_argument("--config", default="config/config.yaml")
    ap.add_argument(
        "--ref",
        default="data/raw/LC08_L1TP_168034_20190524_20200828_02_T1_B4.TIF",
        help="Reference raster defining target CRS and pixel resolution",
    )
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8")) or {}
    raw_dir = Path(cfg.get("paths", {}).get("raw_data", "data/raw"))
    aligned_dir = Path(cfg.get("paths", {}).get("processed_data", "data/processed")) / "aligned"

    ref_ds = gdal.Open(str(Path(args.ref)), gdal.GA_ReadOnly)
    if ref_ds is None:
        raise FileNotFoundError(f"Reference raster not found: {args.ref}")

    targets = sorted(
        glob.glob(str(raw_dir / "GLDAS_*.tif")) + glob.glob(str(raw_dir / "wc*.tif"))
    )
    if not targets:
        print(f"No GLDAS_*.tif or wc*.tif files found in {raw_dir}")
        return

    for item in targets:
        src_p = Path(item)
        dst_p = aligned_dir / src_p.name
        warp_to_reference(src_p, dst_p, ref_ds)
        print(f"Aligned: {dst_p}")

    ref_ds = None


if __name__ == "__main__":
    main()
