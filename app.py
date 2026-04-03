from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import List, Optional
import uuid
import threading
import os

from main import run, load_config

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# 작업 상태 저장소
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
    # 초기 로그 설정
    jobs[job_id] = {"logs": ["⏳ 서버에서 작업을 준비 중입니다..."], "status": "running", "raw_files": []}

    def log_callback(msg):
        if job_id in jobs:
            jobs[job_id]["logs"].append(str(msg))

    def task():
        try:
            log_callback(f"🚀 {year}년 {quarter}분기 수집 작업을 시작합니다.")
            
            config = load_config("config.yaml")
            config["period"]["year"] = year
            config["period"]["quarter"] = quarter

            if api_key:
                config["dart"]["api_key"] = api_key

            config["companies"] = [
                c for c in config["companies"]
                if c["short_name"] in companies
            ]

            # main.py의 run 실행
            result = run(config, log_callback)

            # 성공 시 결과 저장
            jobs[job_id]["file"] = result["excel"]
            jobs[job_id]["raw_files"] = result.get("raw_files", [])
            jobs[job_id]["status"] = "done"
            log_callback("✅ 모든 작업이 완료되었습니다!")

        except Exception as e:
            # 💡 에러 발생 시 로그에 상세 내용을 남깁니다.
            import traceback
            error_detail = traceback.format_exc()
            print(error_detail)  # Render 서버 로그 확인용
            log_callback(f"❌ 오류 발생: {str(e)}")
            jobs[job_id]["status"] = "error"

    # 백그라운드 스레드 실행
    thread = threading.Thread(target=task)
    thread.start()

    return {"job_id": job_id}

@app.get("/status/{job_id}")
def status(job_id: str):
    # 해당 작업 ID가 없으면 기본값 반환
    return jobs.get(job_id, {"logs": ["작업을 찾을 수 없습니다."], "status": "error"})

@app.get("/download_raw/{job_id}")
def download_raw(job_id: str):
    job = jobs.get(job_id)
    if not job or not job.get("raw_files"):
        return JSONResponse({"error": "원본 파일을 찾을 수 없습니다."}, status_code=404)

    raw_files = [p for p in job.get("raw_files", []) if os.path.exists(p)]
    if not raw_files:
        return JSONResponse({"error": "서버에 원본 파일이 존재하지 않습니다."}, status_code=404)

    import zipfile
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        zip_path = os.path.join(td, f"raw_reports_{job_id}.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in raw_files:
                zf.write(p, arcname=os.path.basename(p))

        return FileResponse(
            path=zip_path,
            filename=f"raw_reports_{job_id}.zip",
            media_type='application/zip'
        )

@app.get("/download/{job_id}")
def download_file(job_id: str):
    job = jobs.get(job_id)
    if not job or "file" not in job:
        return JSONResponse({"error": "파일을 찾을 수 없습니다."}, status_code=404)
    
    file_path = job["file"]
    if os.path.exists(file_path):
        return FileResponse(
            path=file_path, 
            filename=os.path.basename(file_path),
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    return JSONResponse({"error": "서버에 파일이 존재하지 않습니다."}, status_code=404)