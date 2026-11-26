import argparse, os, sys
from pathlib import Path

ENV_BIN = Path(sys.prefix) / "Library" / "bin"
if os.name == "nt" and ENV_BIN.exists():
    os.environ["PATH"] = f"{ENV_BIN};{os.environ.get('PATH', '')}"
    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(str(ENV_BIN))

import matplotlib.pyplot as plt
import numpy as np, yaml
from osgeo import gdal

gdal.UseExceptions()

def load_raster(path: Path) -> np.ndarray:
    ds = gdal.Open(str(path), gdal.GA_ReadOnly)
    if ds is None:
        raise FileNotFoundError(f"Raster not found: {path}")
    b = ds.GetRasterBand(1)
    nd = b.GetNoDataValue()
    arr = b.ReadAsArray().astype(np.float32)
    mask = ~np.isfinite(arr) | (np.isclose(arr, float(nd)) if nd is not None else False)
    arr[mask] = np.nan
    ds = None
    return arr

def make_pair_plot(var_title: str, unit: str, cmap: str, vmin: float, vmax: float,
                   p_may: Path, p_jul: Path, out_png: Path):
    a_may, a_jul = load_raster(p_may), load_raster(p_jul)
    diff = a_jul - a_may
    d_lim = max(float(np.nanpercentile(np.abs(diff), 98)), 0.1)

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6), constrained_layout=True)
    panels = [
        (a_may, f"2019-05-24 ({unit})", cmap, vmin, vmax),
        (a_jul, f"2019-07-27 ({unit})", cmap, vmin, vmax),
        (diff, f"July - May ({unit})", "RdBu_r", -d_lim, d_lim),
    ]
    for ax, (data, title, cm, lo, hi) in zip(axes, panels):
        im = ax.imshow(data, cmap=cm, vmin=lo, vmax=hi)
        ax.set_title(title)
        ax.set_xticks([])
        ax.set_yticks([])
        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    fig.suptitle(f"{var_title} Comparison — Landsat 8 (Path/Row 168034)", fontsize=13)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=180)
    plt.close(fig)
    print(f"Saved figure: {out_png}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/config.yaml")
    cfg = yaml.safe_load(Path(ap.parse_args().config).read_text(encoding="utf-8")) or {}
    out_base = Path(cfg.get("paths", {}).get("outputs", "data/outputs"))
    fig_dir = out_base / "postprocessed" / "figures"

    make_pair_plot(
        "Daily Actual ET (ETact_24)", "mm/day", "YlGnBu", 0.0, 9.0,
        out_base / "scene_20190524" / "Output_evapotranspiration" / "L8_ETact_24_30m_2019_05_24_144.tif",
        out_base / "scene_20190727" / "Output_evapotranspiration" / "L8_ETact_24_30m_2019_07_27_208.tif",
        fig_dir / "etact_24_may_vs_jul_2019.png",
    )
    make_pair_plot(
        "NDVI", "index", "RdYlGn", -0.2, 0.8,
        out_base / "scene_20190524" / "Output_vegetation" / "L8_NDVI_30m_2019_05_24_144.tif",
        out_base / "scene_20190727" / "Output_vegetation" / "L8_NDVI_30m_2019_07_27_208.tif",
        out_base / "scene_20190727" / "Output_vegetation" / "L8_NDVI_30m_2019_07_27_208.tif",
        fig_dir / "ndvi_may_vs_jul_2019.png",
    )
    make_pair_plot(
        "Crop Coefficient (kc)", "ratio", "YlGn", 0.0, 1.5,
        out_base / "scene_20190524" / "Output_evapotranspiration" / "L8_kc_30m_2019_05_24_144.tif",
        out_base / "scene_20190727" / "Output_evapotranspiration" / "L8_kc_30m_2019_07_27_208.tif",
        fig_dir / "kc_may_vs_jul_2019.png",
    )
    make_pair_plot(
        "Daily Biomass Production", "kg/ha/day", "YlGn", 0.0, 150.0,
        out_base / "scene_20190524" / "Output_biomass_production" / "L8_Biomass_production_30m_2019_05_24_144.tif",
        out_base / "scene_20190727" / "Output_biomass_production" / "L8_Biomass_production_30m_2019_07_27_208.tif",
        fig_dir / "biomass_production_may_vs_jul_2019.png",
    )



if __name__ == "__main__":
    main()
