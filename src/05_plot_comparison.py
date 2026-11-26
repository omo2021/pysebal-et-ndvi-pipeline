import argparse
import os
import sys
from pathlib import Path

ENV_BIN = Path(sys.prefix) / "Library" / "bin"
if os.name == "nt" and ENV_BIN.exists():
    os.environ["PATH"] = f"{ENV_BIN};{os.environ.get('PATH', '')}"
    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(str(ENV_BIN))

import matplotlib.pyplot as plt
import numpy as np
import yaml
from osgeo import gdal

gdal.UseExceptions()


def read_band(tif_path: Path, step: int = 4) -> np.ndarray:
    ds = gdal.Open(str(tif_path), gdal.GA_ReadOnly)
    if ds is None:
        raise RuntimeError(f"Could not open raster: {tif_path}")
    b = ds.GetRasterBand(1)
    nd = b.GetNoDataValue()
    arr = b.ReadAsArray()[::step, ::step].astype(np.float32)
    bad = ~np.isfinite(arr) | (np.isclose(arr, float(nd)) if nd is not None else False)
    arr[bad] = np.nan
    ds = None
    return arr


def make_pair_plot(
    title: str,
    unit: str,
    cmap: str,
    vmin: float,
    vmax: float,
    p_may: Path,
    p_jul: Path,
    out_png: Path,
) -> None:
    a_may = read_band(p_may)
    a_jul = read_band(p_jul)
    diff = a_jul - a_may
    d_lim = float(np.nanpercentile(np.abs(diff), 98)) if np.isfinite(diff).any() else 1.0
    d_lim = max(d_lim, 0.1)

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6), constrained_layout=True)
    panels = [
        (a_may, "2019-05-24 (DOY 144)", cmap, vmin, vmax),
        (a_jul, "2019-07-27 (DOY 208)", cmap, vmin, vmax),
        (diff, "July minus May", "RdBu", -d_lim, d_lim),
    ]
    for ax, (data, subtitle, cm, lo, hi) in zip(axes, panels):
        im = ax.imshow(data, cmap=cm, vmin=lo, vmax=hi)
        ax.set_title(subtitle)
        ax.set_xticks([])
        ax.set_yticks([])
        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label(unit)

    fig.suptitle(f"{title} Comparison (2019)", fontsize=13)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(out_png), dpi=160)
    plt.close(fig)
    print(f"Saved preview figure: {out_png}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/config.yaml")
    cfg = yaml.safe_load(Path(ap.parse_args().config).read_text(encoding="utf-8")) or {}
    out_base = Path(cfg.get("paths", {}).get("outputs", "data/outputs"))
    fig_dir = Path("docs/figures")
    fig_dir.mkdir(parents=True, exist_ok=True)

    pairs = [
        (
            "Actual ET (ETact_24)",
            "mm/day",
            "YlGnBu",
            0.0,
            8.0,
            out_base / "scene_20190524" / "Output_evapotranspiration" / "L8_ETact_24_30m_2019_05_24_144.tif",
            out_base / "scene_20190727" / "Output_evapotranspiration" / "L8_ETact_24_30m_2019_07_27_208.tif",
            fig_dir / "etact_24_may_vs_jul_2019.png",
        ),
        (
            "NDVI",
            "index",
            "RdYlGn",
            -0.2,
            0.8,
            out_base / "scene_20190524" / "Output_vegetation" / "L8_NDVI_30m_2019_05_24_144.tif",
            out_base / "scene_20190727" / "Output_vegetation" / "L8_NDVI_30m_2019_07_27_208.tif",
            fig_dir / "ndvi_may_vs_jul_2019.png",
        ),
        (
            "Crop Coefficient (kc)",
            "ratio",
            "YlGn",
            0.0,
            1.5,
            out_base / "scene_20190524" / "Output_evapotranspiration" / "L8_kc_30m_2019_05_24_144.tif",
            out_base / "scene_20190727" / "Output_evapotranspiration" / "L8_kc_30m_2019_07_27_208.tif",
            fig_dir / "kc_may_vs_jul_2019.png",
        ),
        (
            "Daily Biomass Production",
            "kg/ha/day",
            "YlGn",
            0.0,
            150.0,
            out_base / "scene_20190524" / "Output_biomass_production" / "L8_Biomass_production_30m_2019_05_24_144.tif",
            out_base / "scene_20190727" / "Output_biomass_production" / "L8_Biomass_production_30m_2019_07_27_208.tif",
            fig_dir / "biomass_production_may_vs_jul_2019.png",
        ),
    ]

    for title, unit, cmap, vmin, vmax, p_may, p_jul, out_png in pairs:
        if p_may.exists() and p_jul.exists():
            make_pair_plot(title, unit, cmap, vmin, vmax, p_may, p_jul, out_png)
        else:
            print(f"Skipping {out_png.name}: missing input raster")


if __name__ == "__main__":
    main()