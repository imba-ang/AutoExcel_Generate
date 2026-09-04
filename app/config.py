from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    template_path: Path
    teacher_password: str
    session_secret: str
    public_base_url: str | None
    cookie_secure: bool
    qr_base_url: str | None = None

    @property
    def db_path(self) -> Path:
        return self.data_dir / "submissions.db"

    @property
    def uses_insecure_defaults(self) -> bool:
        return self.teacher_password == "change-me-now" or len(self.session_secret) < 32

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = Path(os.getenv("DATA_DIR", BASE_DIR / "data")).expanduser().resolve()
        template_path = Path(
            os.getenv("EXCEL_TEMPLATE_PATH", BASE_DIR / "app" / "assets" / "template.xlsx")
        ).expanduser().resolve()
        public_base_url = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/") or None
        qr_base_url = os.getenv("QR_BASE_URL", "").strip().rstrip("/") or None
        return cls(
            data_dir=data_dir,
            template_path=template_path,
            teacher_password=os.getenv("TEACHER_PASSWORD", "change-me-now"),
            session_secret=os.getenv("SESSION_SECRET", secrets.token_urlsafe(32)),
            public_base_url=public_base_url,
            cookie_secure=os.getenv("COOKIE_SECURE", "false").lower() in {"1", "true", "yes"},
            qr_base_url=qr_base_url,
        )
