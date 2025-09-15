from fastapi import FastAPI, File, UploadFile, HTTPException, Request, APIRouter, Form, BackgroundTasks
from fastapi.responses import JSONResponse, Response
import shutil
import os
import json
import uuid
# Lazy import to prevent startup crashes

app = FastAPI()

UPLOAD_FOLDER = "./uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Simple configuration (can be moved to config/env as needed)
ALLOWED_EXTENSIONS = {".pdf"}
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))


@app.middleware("http")
async def log_requests(request: Request, call_next):
    from time import perf_counter
    start = perf_counter()
    try:
        response = await call_next(request)
        return response
    finally:
        duration_ms = (perf_counter() - start) * 1000
        method = request.method
        path = request.url.path
        status = getattr(request.state, "_status", None) or (response.status_code if 'response' in locals() else '-')
        print(f"{method} {path} -> {status} in {duration_ms:.1f}ms")


v1 = APIRouter(prefix="/v1")

@app.get("/")
async def root():
    return {"status": "ok", "message": "Rule Extractor API"}

async def _post_webhook(webhook_url: str, body: str, job_id: str | None = None):
    try:
        import httpx
        headers = {"Content-Type": "application/json", "X-Event": "rules.extracted.v1"}
        if job_id:
            headers["X-Job-Process-Id"] = job_id
        # fire-and-forget with short timeout
        with httpx.Client(timeout=15.0) as client:
            client.post(webhook_url, data=body.encode("utf-8"), headers=headers)
    except Exception as _:
        # Intentionally swallow errors to avoid impacting API response
        pass


@v1.post("/extract")
async def extract_rules_v1(
    request: Request,
    file: UploadFile = File(...),
    webhook_url: str | None = Form(default=None),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    # Validate extension
    _, ext = os.path.splitext(file.filename)
    if ext.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail={"error": "unsupported_file_type", "code": "bad_request"})

    file_location = os.path.join(UPLOAD_FOLDER, file.filename)
    with open(file_location, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        # Size check after write
        size_mb = os.path.getsize(file_location) / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            os.remove(file_location)
            raise HTTPException(status_code=413, detail={"error": "file_too_large", "code": "payload_too_large"})

        # If webhook_url provided, run asynchronously and return job_process_id immediately
        if webhook_url:
            job_id = str(uuid.uuid4())

            async def _process_and_notify():
                status_payload = {"job_process_id": job_id, "status": "failure", "error": "unknown"}
                try:
                    from .main import main
                    main(file_location)
                    output_file_inner = file_location.rsplit(".", 1)[0] + "_rules.json"
                    if not os.path.exists(output_file_inner):
                        status_payload = {"job_process_id": job_id, "status": "failure", "error": "output_not_found"}
                    else:
                        with open(output_file_inner, "r") as f:
                            rules_inner = json.load(f)
                        status_payload = {"job_process_id": job_id, "status": "success", "rules": rules_inner}
                except Exception as e:  # noqa: BLE001
                    status_payload = {"job_process_id": job_id, "status": "failure", "error": str(e)}
                # Post to webhook
                await _post_webhook(webhook_url, json.dumps(status_payload, ensure_ascii=False), job_id)

            background_tasks.add_task(_process_and_notify)

            return JSONResponse(status_code=202, content={"job_process_id": job_id})

        # Otherwise, run synchronously and return rules directly
        from .main import main
        main(file_location)
        output_file = file_location.rsplit(".", 1)[0] + "_rules.json"
        if not os.path.exists(output_file):
            return JSONResponse(status_code=500, content={"error": "output_not_found", "code": "internal_error"})
        with open(output_file, "r") as f:
            rules = json.load(f)
        body = json.dumps(rules, indent=2, ensure_ascii=False)
        return Response(content=body, media_type="application/json")
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": "internal_error", "code": "internal_error", "message": str(e)})

@v1.get("/health")
async def health_v1():
    return {"status": "healthy"}


app.include_router(v1)