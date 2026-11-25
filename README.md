# PySEBAL ET & NDVI Pipeline

A step-by-step Python workflow to calculate **Evapotranspiration (ET)**, **Biomass**, and **NDVI** using **PySEBAL**, followed by monthly averaging, spatio-temporal gap-filling, and seasonal/annual aggregation.

## Workflow Overview
1. **Input Data Acquisition:** Satellite imagery (e.g., Landsat), DEM, meteorological data, and soil data.
2. **PySEBAL Processing:** Per-image calculation of ET, NDVI, and Biomass.
3. **Post-Processing:** Monthly maps, spatio-temporal gap-filling, and seasonal/annual aggregation.

## Repository Structure
- `config/` – Configuration settings (study area, dates, paths)
- `src/` – Python scripts for preprocessing, PySEBAL execution, and post-processing
- `data/` – Local data folder (ignored by Git)

## Status
Work in progress — building step by step.
