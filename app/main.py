"""应用入口。"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.database import Base, engine, run_teacher_migrations
from app.routers import student, teacher

app = FastAPI(title=settings.project_name)

templates = Jinja2Templates(directory=str(settings.base_dir / "app" / "templates"))
app.mount("/static", StaticFiles(directory=str(settings.base_dir / "app" / "static")), name="static")
app.mount("/uploads", StaticFiles(directory=str(settings.upload_dir)), name="uploads")


@app.on_event("startup")
def on_startup() -> None:
    """启动时创建数据库表。"""

    Base.metadata.create_all(bind=engine)
    run_teacher_migrations()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request, "title": settings.project_name})


@app.get("/teacher", response_class=HTMLResponse)
def teacher_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("teacher.html", {"request": request, "title": settings.project_name})


@app.get("/student", response_class=HTMLResponse)
def student_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("student.html", {"request": request, "title": settings.project_name})


app.include_router(teacher.router)
app.include_router(student.router)
