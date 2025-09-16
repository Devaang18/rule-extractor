import functions_framework
import json
import uuid
import httpx
import tempfile
import os
import asyncio

# Import our existing rule extraction logic
from rule_extractor.main import main as extract_rules

# Configuration
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

async def download_and_validate_file(file_url: str) -> str:
    """Download file from URL and return temporary file path"""
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        response = await client.get(file_url)
        response.raise_for_status()
        
        # Check file size
        content_length = response.headers.get('content-length')
        if content_length and int(content_length) > MAX_FILE_SIZE_BYTES:
            raise Exception(f"File size exceeds the limit of {MAX_FILE_SIZE_MB}MB.")
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        temp_file.write(response.content)
        temp_file.close()
        
        return temp_file.name

async def send_webhook(webhook_url: str, payload: dict, job_id: str, event_type: str):
    """Send webhook notification"""
    try:
        headers = {
            "Content-Type": "application/json", 
            "X-Event": event_type,
            "X-Job-Process-Id": job_id
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                webhook_url, 
                json=payload, 
                headers=headers
            )
            print(f"Webhook sent: {event_type} -> {response.status_code}")
            return response.status_code == 200
    except Exception as e:
        print(f"Webhook error: {e}")
        return False

@functions_framework.http
def extract_rules_function(request):
    """Main Cloud Function with multiple endpoints"""
    try:
        # Route based on path
        path = request.path
        method = request.method
        
        # Health check endpoint
        if path == "/health" or path == "/v1/health":
            return {"status": "healthy"}, 200
        
        # Root endpoint
        if path == "/" and method == "GET":
            return {
                "message": "Rule Extractor API - Cloud Functions",
                "endpoints": {
                    "health": "GET /health",
                    "extract": "POST /extract"
                }
            }, 200
        
        # Extract endpoint
        if path == "/extract" or path == "/v1/extract" or path == "/":
            if method != "POST":
                return {"error": "Method not allowed"}, 405
                
            # Parse request
            request_json = request.get_json()
            if not request_json:
                return {"error": "Invalid JSON body"}, 400
                
            file_url = request_json.get('file_url')
            webhook_url = request_json.get('webhook_url')
            
            if not file_url or not webhook_url:
                return {"error": "Missing file_url or webhook_url"}, 400
            
            # Generate job ID
            job_id = str(uuid.uuid4())
            print(f"Starting job {job_id}")
            
              # IMMEDIATE RESPONSE - Return job ID right away
            import threading
            
            def process_in_background():
                """Background processing that runs after response is sent"""
                async def process_with_webhooks():
                    # 1. Send immediate webhook
                    immediate_payload = {
                        "job_process_id": job_id,
                        "status": "processing",
                        "message": "Job received and processing started"
                    }
                    await send_webhook(webhook_url, immediate_payload, job_id, "rules.processing.v1")
                    
                    # 2. Process the PDF
                    temp_file_path = None
                    try:
                        # Download and process
                        temp_file_path = await download_and_validate_file(file_url)
                        print(f"Processing PDF: {temp_file_path}")
                        
                        rules_json = extract_rules(temp_file_path)
                        rules = json.loads(rules_json)
                        
                        # 3. Send success webhook
                        success_payload = {
                            "job_process_id": job_id,
                            "status": "success",
                            "rules": rules
                        }
                        await send_webhook(webhook_url, success_payload, job_id, "rules.extracted.v1")
                        print(f"Job {job_id} completed successfully")
                        
                    except Exception as e:
                        # 3. Send failure webhook
                        failure_payload = {
                            "job_process_id": job_id,
                            "status": "failure",
                            "error": str(e)
                        }
                        await send_webhook(webhook_url, failure_payload, job_id, "rules.extraction.failed.v1")
                        print(f"Job {job_id} failed: {e}")
                        
                    finally:
                        # Clean up
                        if temp_file_path and os.path.exists(temp_file_path):
                            os.unlink(temp_file_path)
                
                # Run the async processing
                asyncio.run(process_with_webhooks())
            
            # Start background thread
            thread = threading.Thread(target=process_in_background)
            thread.daemon = True
            thread.start()
            
            # Return immediately with job ID
            return {"job_process_id": job_id}, 202
        
        # Unknown endpoint
        return {"error": "Endpoint not found"}, 404
        
    except Exception as e:
        print(f"Function error: {e}")
        return {"error": str(e)}, 500
