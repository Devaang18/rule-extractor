from fastapi import FastAPI, File, UploadFile, HTTPException, Request, APIRouter
from fastapi.responses import JSONResponse, Response
import shutil
import os
import json
from .main import main  # import your existing main rule extraction function

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

@v1.post("/extract")
async def extract_rules_v1(request: Request, file: UploadFile = File(...)):
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

        main(file_location)
        output_file = file_location.rsplit(".", 1)[0] + "_rules.json"
        if not os.path.exists(output_file):
            return JSONResponse(status_code=500, content={"error": "output_not_found", "code": "internal_error"})
        with open(output_file, "r") as f:
            rules = json.load(f)
        # Return just the array of rules (no outer object), pretty-printed
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