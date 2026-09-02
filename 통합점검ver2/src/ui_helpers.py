from __future__ import annotations

import pandas as pd


def display_value(value: object) -> str:
    if value is None or pd.isna(value) or str(value).strip() in {"", "nan", "NaN"}:
        return "-"
    return str(value).strip()


def display_frame(frame: pd.DataFrame, columns: dict[str, str]) -> pd.DataFrame:
    available = [column for column in columns if column in frame.columns]
    result = frame[available].copy().fillna("")
    for column in available:
        result[column] = result[column].map(display_value)
    return result.rename(columns={column: columns[column] for column in available})
