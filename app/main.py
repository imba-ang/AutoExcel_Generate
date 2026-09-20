from __future__ import annotations

import hmac
import io
import re
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app.config import BASE_DIR, Settings
from app.db import (
    get_student,
    init_db,
    list_students,
    load_answers,
    load_submission,
    save_submission,
)
from app.security import COOKIE_NAME, SESSION_SECONDS, make_teacher_token, verify_teacher_token
from app.template_service import SECTIONS, ExcelTemplate


class SubmissionPayload(BaseModel):
    student_name: str = Field(min_length=1, max_length=40)
    student_id: str = Field(min_length=1, max_length=40)
    answers: dict[str, str]


def clean_identity(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def validate_payload(payload: SubmissionPayload, section: str) -> tuple[str, str, dict[str, str]]:
    student_name = clean_identity(payload.student_name)
    student_id = clean_identity(payload.student_id)
    if not student_name or not student_id:
        raise HTTPException(status_code=422, detail="姓名和学号均不能为空。")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", student_id):
        raise HTTPException(status_code=422, detail="学号只能包含数字、字母、横线或下划线。")
    allowed = set(SECTIONS[section].editable_cells)
    answers = {
        coordinate: str(value).strip()[:2000]
        for coordinate, value in payload.answers.items()
        if coordinate in allowed
    }
    if sum(len(value) for value in answers.values()) > 20000:
        raise HTTPException(status_code=422, detail="填写内容过长，请精简后再提交。")
    return student_name, student_id, answers


def attachment_headers(filename: str) -> dict[str, str]:
    return {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings.from_env()
    excel_template = ExcelTemplate(config.template_path)
    templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))
    templates.env.filters["display_time"] = lambda value: (
        str(value).replace("T", " ").split("+")[0] if value else "—"
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        init_db(config.db_path)
        yield

    app = FastAPI(title="创意有方在线填写", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://imba-ang.github.io"],
        allow_methods=["POST"],
        allow_headers=["Content-Type"],
    )
    app.state.settings = config
    app.state.excel_template = excel_template
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")

    def teacher_logged_in(request: Request) -> bool:
        return verify_teacher_token(request.cookies.get(COOKIE_NAME), config.session_secret)

    def teacher_redirect(request: Request) -> RedirectResponse | None:
        if teacher_logged_in(request):
            return None
        return RedirectResponse(url="/teacher/login", status_code=303)

    def qr_base_url(request: Request) -> str:
        return config.qr_base_url or config.public_base_url or str(request.base_url).rstrip("/")

    def template_context(request: Request, **extra):
        return {
            "request": request,
            "sections": excel_template.sections,
            **extra,
        }

    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="home.html",
            context=template_context(request),
        )

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/student/{section}", response_class=HTMLResponse)
    async def student_form(request: Request, section: str):
        if section not in SECTIONS:
            raise HTTPException(status_code=404, detail="表格类型不存在。")
        spec = excel_template.spec(section)
        return templates.TemplateResponse(
            request=request,
            name="student.html",
            context=template_context(
                request,
                section=spec,
                rows=excel_template.render_rows(section),
                column_widths=excel_template.column_widths(),
            ),
        )

    @app.post("/api/submissions/{section}/load")
    async def load_student_submission(section: str, payload: SubmissionPayload):
        if section not in SECTIONS:
            raise HTTPException(status_code=404, detail="表格类型不存在。")
        student_name, student_id, _ = validate_payload(payload, section)
        try:
            record = load_submission(config.db_path, student_id, student_name, section)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        context_answers = load_answers(config.db_path, student_id, "kuo") if section == "shai" else {}
        return {
            "exists": record is not None,
            "answers": record["answers"] if record else {},
            "updated_at": record["updated_at"] if record else None,
            "context_answers": context_answers,
        }

    @app.post("/api/submissions/{section}")
    async def submit_student_form(section: str, payload: SubmissionPayload):
        if section not in SECTIONS:
            raise HTTPException(status_code=404, detail="表格类型不存在。")
        student_name, student_id, answers = validate_payload(payload, section)
        try:
            updated_at = save_submission(
                config.db_path, student_id, student_name, section, answers
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {"ok": True, "updated_at": updated_at, "mode": "upsert"}

    @app.get("/teacher/login", response_class=HTMLResponse)
    async def teacher_login_page(request: Request, error: str | None = None):
        if teacher_logged_in(request):
            return RedirectResponse(url="/teacher", status_code=303)
        return templates.TemplateResponse(
            request=request,
            name="teacher_login.html",
            context=template_context(request, error=error),
        )

    @app.post("/teacher/login")
    async def teacher_login(password: str = Form(...)):
        if not hmac.compare_digest(password, config.teacher_password):
            return RedirectResponse(url="/teacher/login?error=密码错误", status_code=303)
        response = RedirectResponse(url="/teacher", status_code=303)
        response.set_cookie(
            COOKIE_NAME,
            make_teacher_token(config.session_secret),
            max_age=SESSION_SECONDS,
            httponly=True,
            secure=config.cookie_secure,
            samesite="lax",
        )
        return response

    @app.post("/teacher/logout")
    async def teacher_logout():
        response = RedirectResponse(url="/teacher/login", status_code=303)
        response.delete_cookie(COOKIE_NAME)
        return response

    @app.get("/teacher", response_class=HTMLResponse)
    async def teacher_dashboard(request: Request, q: str = "", status: str = "all"):
        redirect = teacher_redirect(request)
        if redirect:
            return redirect
        students = list_students(config.db_path)
        query = q.strip().lower()
        if query:
            students = [
                row for row in students
                if query in row["student_id"].lower() or query in row["student_name"].lower()
            ]
        if status in SECTIONS:
            students = [row for row in students if row[f"{status}_updated_at"]]
        elif status.startswith("missing-") and status.removeprefix("missing-") in SECTIONS:
            slug = status.removeprefix("missing-")
            students = [row for row in students if not row[f"{slug}_updated_at"]]
        return templates.TemplateResponse(
            request=request,
            name="teacher_dashboard.html",
            context=template_context(
                request,
                students=students,
                query=q,
                status=status,
                insecure_defaults=config.uses_insecure_defaults,
            ),
        )

    @app.get("/teacher/student/{student_id}/{section}", response_class=HTMLResponse)
    async def teacher_submission(request: Request, student_id: str, section: str):
        redirect = teacher_redirect(request)
        if redirect:
            return redirect
        if section not in SECTIONS:
            raise HTTPException(status_code=404, detail="表格类型不存在。")
        student = get_student(config.db_path, student_id)
        if not student:
            raise HTTPException(status_code=404, detail="学生不存在。")
        answers = load_answers(config.db_path, student_id, section)
        if not answers:
            raise HTTPException(status_code=404, detail="该表尚未提交。")
        context_answers = load_answers(config.db_path, student_id, "kuo")
        return templates.TemplateResponse(
            request=request,
            name="teacher_submission.html",
            context=template_context(
                request,
                student=student,
                section=excel_template.spec(section),
                rows=excel_template.render_rows(
                    section, answers=answers, context_answers=context_answers, readonly=True
                ),
                column_widths=excel_template.column_widths(),
            ),
        )

    def workbook_for_student(student_id: str) -> tuple[dict[str, str], io.BytesIO]:
        student = get_student(config.db_path, student_id)
        if not student:
            raise HTTPException(status_code=404, detail="学生不存在。")
        all_answers = {slug: load_answers(config.db_path, student_id, slug) for slug in SECTIONS}
        return student, excel_template.build_workbook(all_answers)

    @app.get("/teacher/download/{student_id}")
    async def download_student(request: Request, student_id: str):
        redirect = teacher_redirect(request)
        if redirect:
            return redirect
        student, output = workbook_for_student(student_id)
        filename = f"{student['student_id']}_{student['student_name']}_创新方案.xlsx"
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers=attachment_headers(filename),
        )

    @app.get("/teacher/download-all")
    async def download_all(request: Request):
        redirect = teacher_redirect(request)
        if redirect:
            return redirect
        output = io.BytesIO()
        with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            for student in list_students(config.db_path):
                _, workbook = workbook_for_student(student["student_id"])
                filename = f"{student['student_id']}_{student['student_name']}_创新方案.xlsx"
                archive.writestr(filename, workbook.getvalue())
        output.seek(0)
        return StreamingResponse(
            output,
            media_type="application/zip",
            headers=attachment_headers("全班创新方案.zip"),
        )

    @app.get("/teacher/qrcodes", response_class=HTMLResponse)
    async def teacher_qrcodes(request: Request):
        redirect = teacher_redirect(request)
        if redirect:
            return redirect
        base_url = qr_base_url(request)
        qr_items = [
            {
                "section": spec,
                "url": f"{base_url}/student/{spec.slug}",
                "image_url": f"/teacher/qrcode/{spec.slug}.png",
            }
            for spec in excel_template.sections
        ]
        return templates.TemplateResponse(
            request=request,
            name="teacher_qrcodes.html",
            context=template_context(request, qr_items=qr_items, public_base_url=base_url),
        )

    @app.get("/teacher/qrcode/{section}.png")
    async def teacher_qrcode_image(request: Request, section: str, download: bool = False):
        redirect = teacher_redirect(request)
        if redirect:
            return redirect
        if section not in SECTIONS:
            raise HTTPException(status_code=404, detail="表格类型不存在。")
        import qrcode

        target = f"{qr_base_url(request)}/student/{section}"
        image = qrcode.make(target)
        output = io.BytesIO()
        image.save(output, format="PNG")
        headers = attachment_headers(f"{SECTIONS[section].label}二维码.png") if download else {}
        return Response(content=output.getvalue(), media_type="image/png", headers=headers)

    return app


app = create_app()
