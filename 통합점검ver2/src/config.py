import os
from pathlib import Path

from src.env import load_project_env


load_project_env()

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = PROJECT_ROOT / "data" / "private" / "input"
DATA_BACKEND = os.getenv("DATA_BACKEND", "local").strip().lower()

COMPANIES_FILE = "01_companies.csv"
INSPECTIONS_FILE = "02_inspections.csv"
DISPOSITIONS_FILE = "03_dispositions.csv"
ALIASES_FILE = "04_company_aliases.csv"

REQUIRED_COLUMNS = {
    COMPANIES_FILE: {"company_id", "company_name", "permit_number", "address"},
    INSPECTIONS_FILE: {"inspection_id", "company_id", "inspection_date"},
    DISPOSITIONS_FILE: {"disposition_id", "company_id", "disposition_date"},
    ALIASES_FILE: {"company_id", "alias_value", "normalized_value"},
}
