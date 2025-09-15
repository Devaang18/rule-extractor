# Rule Extractor API
Minimal FastAPI service that extracts rules from a PDF and returns a JSON array.

## Quickstart

1. Python 3.11
2. Create venv and install deps:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r rule_extractor/requirements.txt
```

3. Set env (copy .env.sample → .env and fill `OPENAI_API_KEY`).

4. Run:

```bash
uvicorn rule_extractor.app:app --reload --env-file .env
```

5. Test:

```bash
curl http://127.0.0.1:8000/v1/health
curl -X POST http://127.0.0.1:8000/v1/extract -F file=@/absolute/path/to/file.pdf -o out.json
```

## Response

- Returns a JSON array of rules (pretty-printed), each with:
  - rule_id (UUID)
  - rule_text, context, tags (list)
  - category ∈ {Marketing, Gambling, Legal, Compliance}
  - metadata.source_document (filename sans extension)

## Deployment (Cloud Run)

- Build an image and deploy to Cloud Run.
- For many clients, put Cloud Run behind API Gateway. Require `x-api-key` in the gateway config.
- Your service code does not need to manage client keys.

## Notes

- File type: PDF only
- Max file size: configurable via `MAX_FILE_SIZE_MB` (default 50)
- Logging: basic request logs with method, path, status, latency
