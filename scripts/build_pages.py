from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import BASE_DIR, Settings
from app.main import create_app


PAGES_PATH = "/AutoExcel_Generate"
PAGES_URL = "https://imba-ang.github.io/AutoExcel_Generate"
API_BASE = "https://autoexcel-generate-production.up.railway.app"
OUTPUT_DIR = BASE_DIR / "docs"


def rewrite_links(html: str, section: str | None = None) -> str:
    replacements = {
        'href="/static/style.css"': f'href="{PAGES_PATH}/static/style.css"',
        'src="/static/student.js"': f'src="{PAGES_PATH}/static/student.js"',
        'href="/"': f'href="{PAGES_PATH}/"',
        'href="/teacher/login"': f'href="{API_BASE}/teacher/login"',
    }
    for slug in ("qidian", "po", "kuo", "shai"):
        replacements[f'href="/student/{slug}"'] = (
            f'href="{PAGES_PATH}/student/{slug}/"'
        )
    for old, new in replacements.items():
        html = html.replace(old, new)
    if section:
        html = html.replace(
            f'data-section="{section}"',
            f'data-section="{section}" data-api-base="{API_BASE}"',
        )
    return html


def build() -> None:
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    (OUTPUT_DIR / "static").mkdir(parents=True)
    shutil.copy2(BASE_DIR / "app" / "static" / "style.css", OUTPUT_DIR / "static")
    shutil.copy2(BASE_DIR / "app" / "static" / "student.js", OUTPUT_DIR / "static")
    (OUTPUT_DIR / ".nojekyll").write_text("", encoding="utf-8")

    with tempfile.TemporaryDirectory(prefix="autoexcel-pages-") as temp_dir:
        settings = Settings(
            data_dir=Path(temp_dir),
            template_path=BASE_DIR / "app" / "assets" / "template.xlsx",
            teacher_password="pages-build-only",
            session_secret="pages-build-session-secret-longer-than-32-characters",
            public_base_url=PAGES_URL,
            cookie_secure=True,
            qr_base_url=PAGES_URL,
        )
        with TestClient(create_app(settings)) as client:
            home = client.get("/")
            home.raise_for_status()
            (OUTPUT_DIR / "index.html").write_text(
                rewrite_links(home.text), encoding="utf-8"
            )
            for section in ("qidian", "po", "kuo", "shai"):
                response = client.get(f"/student/{section}")
                response.raise_for_status()
                target = OUTPUT_DIR / "student" / section
                target.mkdir(parents=True)
                (target / "index.html").write_text(
                    rewrite_links(response.text, section), encoding="utf-8"
                )


if __name__ == "__main__":
    build()
