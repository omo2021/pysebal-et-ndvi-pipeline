from pathlib import Path
import yaml


def load_config(config_path: str = "config/config.yaml") -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


if __name__ == "__main__":
    cfg = load_config()
    lib_dir = Path(cfg["paths"]["pysebal_lib"])
    run_script = lib_dir / "SEBAL" / "Run_py3.py"
    excel_template = lib_dir / "test_data" / "InputEXCEL_v3_3_7_WIN.xlsx"
    gapfill_script = lib_dir / "gapfilling" / "gapfill_v3.py"

    for label, path in [
        ("PySEBAL lib dir", lib_dir),
        ("Run_py3.py", run_script),
        ("Windows Excel template", excel_template),
        ("Gapfill script", gapfill_script),
    ]:
        print(f"{label}: {path} -> exists={path.exists()}")
