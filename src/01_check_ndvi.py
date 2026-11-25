from pathlib import Path
import numpy as np
import rasterio
import yaml


def load_config(config_path: str = "config/config.yaml") -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def compute_ndvi(red_path: Path, nir_path: Path, out_path: Path) -> None:
    with rasterio.open(red_path) as red_src:
        red = red_src.read(1).astype("float32")
        profile = red_src.profile.copy()

    with rasterio.open(nir_path) as nir_src:
        nir = nir_src.read(1).astype("float32")

    denom = nir + red
    ndvi = np.where(denom != 0, (nir - red) / denom, np.nan).astype("float32")

    profile.update(dtype="float32", count=1, nodata=np.nan)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(ndvi, 1)


if __name__ == "__main__":
    cfg = load_config()
    raw_dir = Path(cfg["paths"]["raw_data"])
    out_dir = Path(cfg["paths"]["outputs"])

    red_file = raw_dir / "red.tif"
    nir_file = raw_dir / "nir.tif"
    ndvi_out = out_dir / "ndvi.tif"

    if red_file.exists() and nir_file.exists():
        compute_ndvi(red_file, nir_file, ndvi_out)
        print(f"Saved NDVI to {ndvi_out}")
    else:
        print(f"Place 'red.tif' and 'nir.tif' in '{raw_dir}' to run NDVI calculation.")