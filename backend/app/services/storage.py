import os
import uuid
from pathlib import Path

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/tmp/opencode/uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def save_upload(data: bytes, filename: str) -> str:
    ext = Path(filename).suffix.lower() or ".bin"
    name = f"{uuid.uuid4().hex}{ext}"
    path = UPLOAD_DIR / name
    path.write_bytes(data)
    return f"/uploads/{name}"
