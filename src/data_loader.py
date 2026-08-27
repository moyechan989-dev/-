from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import (
    ALIASES_FILE,
    COMPANIES_FILE,
    DISPOSITIONS_FILE,
    INPUT_DIR,
    INSPECTIONS_FILE,
    REQUIRED_COLUMNS,
)


def _read_csv(filename: str, input_dir: Path = INPUT_DIR) -> pd.DataFrame:
    path = input_dir / filename
    if not path.exists():
        raise FileNotFoundError(f"필수 CSV 파일을 찾을 수 없습니다: {filename}")
    frame = pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    missing = REQUIRED_COLUMNS[filename] - set(frame.columns)
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise ValueError(f"{filename}에 필수 열이 없습니다: {missing_text}")
    return frame.fillna("")


def load_all_data(input_dir: Path = INPUT_DIR) -> dict[str, pd.DataFrame]:
    """원본 복사 CSV를 읽기만 하며, 어떠한 파일도 변경하지 않는다."""
    return {
        "companies": _read_csv(COMPANIES_FILE, input_dir),
        "inspections": _read_csv(INSPECTIONS_FILE, input_dir),
        "dispositions": _read_csv(DISPOSITIONS_FILE, input_dir),
        "aliases": _read_csv(ALIASES_FILE, input_dir),
    }
