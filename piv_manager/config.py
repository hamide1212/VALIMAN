"""Local application configuration."""

from pathlib import Path
import os


APP_NAME = "VALIMAN"
DATA_DIR = Path(os.environ.get("PIV_MANAGER_DATA_DIR", Path.home() / ".piv_manager"))
DATABASE_PATH = Path(os.environ.get("PIV_MANAGER_DATABASE", DATA_DIR / "piv_manager.sqlite3"))
DOCUMENTS_DIR = Path(os.environ.get("PIV_MANAGER_DOCUMENTS_DIR", DATA_DIR / "documents"))
MAX_DOCUMENT_SIZE = 25 * 1024 * 1024
ALLOWED_DOCUMENT_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt",
    ".png", ".jpg", ".jpeg", ".tif", ".tiff",
}
