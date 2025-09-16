from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl
import os
import json
import uuid
import httpx
import tempfile

app = FastAPI(
    title="Rule Extractor API",
    description="API for extracting rules from PDF documents.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Simple configuration
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

class ExtractRequest(BaseModel):
    file_url: HttpUrl
    webhook_url: HttpUrl

@app.get("/", response_class=JSONResponse)
async def root():
    return {"message": "Welcome to the Rule Extractor API. Visit /v1/health or /v1/extract."}

@app.get("/v1/health", response_class=JSONResponse)
async def health_check():
    return {"status": "healthy"}

async def _download_file_from_url(file_url: str) -> str:
    """Download file from URL and return temporary file path"""
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(file_url)
        response.raise_for_status()
        
        # Check file size
        content_length = response.headers.get('content-length')
        if content_length and int(content_length) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(status_code=413, detail=f"File size exceeds the limit of {MAX_FILE_SIZE_MB}MB.")
        
        # Check content type (be more flexible for Google Drive)
        content_type = response.headers.get('content-type', '').lower()
        print(f"Downloaded file content-type: {content_type}")
        
        # Google Drive sometimes returns different content types, so let's be more flexible
        if not any(x in content_type for x in ['pdf', 'application/octet-stream', 'binary/octet-stream']):
            # Also check if the URL suggests it's a PDF
            if not file_url.lower().endswith('.pdf') and 'drive.google' not in file_url.lower():
                raise HTTPException(status_code=400, detail="Invalid file type. Only PDF files are allowed.")
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        temp_file.write(response.content)
        temp_file.close()
        
        return temp_file.name

async def _post_webhook(webhook_url: str, body: str, job_id: str = None, event_type: str = "rules.extracted.v1"):
    try:
        headers = {"Content-Type": "application/json", "X-Event": event_type}
        if job_id:
            headers["X-Job-Process-Id"] = job_id
        print(f"Sending webhook to {webhook_url} with event {event_type} and job {job_id}")
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(webhook_url, data=body.encode("utf-8"), headers=headers)
            print(f"Webhook response: {response.status_code}")
    except Exception as e:
        print(f"Webhook error: {e}")


@app.post("/v1/extract", response_class=JSONResponse)
async def extract_rules_endpoint(
    extract_request: ExtractRequest,
    background_tasks: BackgroundTasks
):
    # Generate job ID immediately
    job_id = str(uuid.uuid4())
    
    # Send immediate webhook notification (job received)
    immediate_payload = {
        "job_process_id": job_id,
        "status": "processing",
        "message": "Job received and processing started"
    }
    
    # Send immediate webhook synchronously
    await _post_webhook(
        str(extract_request.webhook_url), 
        json.dumps(immediate_payload, ensure_ascii=False), 
        job_id,
        event_type="rules.processing.v1"
    )
    
    async def _process_and_notify():
        status_payload = {"job_process_id": job_id, "status": "failure", "error": "unknown"}
        temp_file_path = None
        
        try:
            print(f"Starting background processing for job {job_id}")
            
            # Download file from URL
            temp_file_path = await _download_file_from_url(str(extract_request.file_url))
            print(f"File downloaded successfully: {temp_file_path}")
            
            # Process the file
            from .main import main
            print(f"Starting rule extraction for {temp_file_path}")
            rules_json = main(temp_file_path)
            rules = json.loads(rules_json)
            status_payload = {"job_process_id": job_id, "status": "success", "rules": rules}
            print(f"Rule extraction completed successfully for job {job_id}")
            
        except Exception as e:
            print(f"Error in background processing for job {job_id}: {e}")
            status_payload = {"job_process_id": job_id, "status": "failure", "error": str(e)}
        
        finally:
            # Clean up temporary file
            if temp_file_path and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                print(f"Cleaned up temporary file: {temp_file_path}")
        
        # Post completion webhook
        event_type = "rules.extracted.v1" if status_payload["status"] == "success" else "rules.extraction.failed.v1"
        print(f"Sending completion webhook for job {job_id} with status {status_payload['status']}")
        await _post_webhook(str(extract_request.webhook_url), json.dumps(status_payload, ensure_ascii=False), job_id, event_type)
        print(f"Completion webhook sent for job {job_id}")

    # Start background processing
    background_tasks.add_task(_process_and_notify)

    # Return immediately with job ID
    return JSONResponse(status_code=202, content={"job_process_id": job_id}, headers={"X-Job-Process-Id": job_id})