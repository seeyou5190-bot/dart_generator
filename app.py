from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import List, Optional
import uuid

from main import run, load_config

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# 작업 상태 저장소 (간단 버전)
jobs = {}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    config = load_config("config.yaml")
    return templates.TemplateResponse(
    request=request,
    name="index.html",
    context={
        "request": request,
        "companies": config["companies"]
    }
)

@app.post("/start")
def start(
    year: int = Form(...),
    quarter: int = Form(...),
    companies: List[str] = Form(...),
    api_key: Optional[str] = Form(None)
):
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"logs": [], "status": "running"}

    def log_callback(msg):
        jobs[job_id]["logs"].append(msg)

    def task():
        config = load_config("config.yaml")
        config["period"]["year"] = year
        config["period"]["quarter"] = quarter

        if api_key:
            config["dart"]["api_key"] = api_key

        config["companies"] = [
            c for c in config["companies"]
            if c["short_name"] in companies
        ]

        path, statements = run(config, log_callback)

        jobs[job_id]["file"] = path
        jobs[job_id]["status"] = "done"
        jobs[job_id]["errors"] = [
            (s.short_name, s.errors) for s in statements if s.errors
        ]

    import threading
    threading.Thread(target=task).start()

    return {"job_id": job_id}


@app.get("/status/{job_id}")
def status(job_id: str):
    return jobs.get(job_id, {})


@app.get("/download/{job_id}")
def download(job_id: str):
    job = jobs[job_id]
    return FileResponse(job["file"], filename="result.xlsx")