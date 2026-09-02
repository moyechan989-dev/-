import os

from src.config import DATA_BACKEND
from src.repositories.base_repository import DataRepository
from src.repositories.local_repository import LocalRepository
from src.repositories.supabase_repository import SupabaseRepository


def create_repository(backend: str | None = None) -> DataRepository:
    selected_backend = (backend or DATA_BACKEND).strip().lower()
    if selected_backend == "local":
        return LocalRepository()
    if selected_backend == "supabase":
        return SupabaseRepository(
            os.getenv("SUPABASE_URL", ""),
            os.getenv("SUPABASE_SECRET_KEY", ""),
        )
    raise ValueError("DATA_BACKEND는 local 또는 supabase여야 합니다.")

__all__ = ["DataRepository", "LocalRepository", "SupabaseRepository", "create_repository"]
