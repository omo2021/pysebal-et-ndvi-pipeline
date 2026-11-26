import argparse
import os
import shutil
import sys
from pathlib import Path

if sys.platform == "win32":
    env_prefix = sys.prefix
    for dll_dir in [
        os.path.join(env_prefix, "Library", "bin"),
        os.path.join(env_prefix, "Library", "mingw-w64", "bin"),
        os.path.join(env_prefix, "Library", "usr", "bin"),
    ]:
        if os.path.isdir(dll_dir):
            os.add_dll_directory(dll_dir)

import openpyxl
import yaml


def load_config(config_path: str = "config/config.yaml") -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _resolve_input_val(val):
    if val is None:
        return None
    if isinstance(val, str):
        candidate = Path(val)
        if candidate.exists():
            return str(candidate.resolve())
    return val


def _apply_sheet_mapping(ws, row_num: int, mapping: dict) -> None:
    if not mapping:
        return
    ws[f"A{row_num}"] = 1
    headers = {
        ws.cell(row=1, column=col).value: col
        for col in range(1, ws.max_column + 1)
        if ws.cell(row=1, column=col).value is not None
    }
    for key, raw_val in mapping.items():
        col = headers.get(key)
        if col is not None and raw_val is not None:
            ws.cell(row=row_num, column=col, value=_resolve_input_val(raw_val))


def build_run_excel(cfg: dict, row_num: int = 2) -> Path:
    lib_dir = Path(cfg["paths"]["pysebal_lib"])
    template_path = lib_dir / "test_data" / "InputEXCEL_v3_3_7_WIN.xlsx"
    processed_dir = Path(cfg["paths"]["processed_data"])
    output_dir = Path(cfg["paths"]["outputs"]) / "pysebal_run"

    processed_dir.mkdir(parents=True, exist_ok=True)
    run_excel = processed_dir / "pysebal_run.xlsx"
    shutil.copy2(template_path, run_excel)

    pysebal_cfg = cfg.get("pysebal", {})
    input_folder = str(Path(pysebal_cfg.get("input_folder", cfg["paths"]["raw_data"])).resolve())
    output_folder = str(Path(pysebal_cfg.get("output_folder", output_dir)).resolve())
    dem_path = str(Path(pysebal_cfg.get("dem_path", lib_dir / "test_data" / "input" / "dem_dal.tif")).resolve())
    image_name = pysebal_cfg.get("image_name", "LC08_L1TP_173049_20140310_20170425_01_T1")

    wb = openpyxl.load_workbook(run_excel)
    meteo_merged = dict(cfg.get("meteo") or {})
    parts = image_name.split("_")
    scene_date = next((tok[:8] for tok in parts if len(tok) >= 8 and tok[:8].isdigit()), "")
    by_date = (cfg.get("meteo_by_date") or {}).get(scene_date) or {}
    meteo_merged.update(by_date)
    _apply_sheet_mapping(wb["Meteo_Input"], row_num, meteo_merged)
    _apply_sheet_mapping(wb["Soil_Input"], row_num, cfg.get("soil", {}))
    ws_gen = wb["General_Input"]
    ws_gen[f"A{row_num}"] = 1
    ws_gen[f"B{row_num}"] = input_folder
    ws_gen[f"C{row_num}"] = output_folder
    ws_gen[f"D{row_num}"] = int(pysebal_cfg.get("image_type", 1))
    ws_gen[f"E{row_num}"] = dem_path

    ws_land = wb["Landsat_Input"]
    ws_land[f"A{row_num}"] = 1
    ws_land[f"B{row_num}"] = image_name
    ws_land[f"C{row_num}"] = int(pysebal_cfg.get("landsat_number", 8))

    wb.save(run_excel)
    return run_excel


def run_sebal(excel_path: Path, lib_dir: Path, row_num: int = 2) -> None:
    sebal_dir = str(lib_dir / "SEBAL")
    if sebal_dir not in sys.path:
        sys.path.insert(0, sebal_dir)

    import pysebal_py3

    pysebal_py3.SEBALcode(row_num, str(excel_path.resolve()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare and optionally run PySEBAL workbook.")
    parser.add_argument("--run", action="store_true", help="Execute pysebal_py3.SEBALcode after preparing Excel.")
    args = parser.parse_args()

    cfg = load_config()
    excel_file = build_run_excel(cfg, row_num=2)
    print(f"Prepared PySEBAL workbook: {excel_file}")

    if args.run:
        run_sebal(excel_file, Path(cfg["paths"]["pysebal_lib"]), row_num=2)