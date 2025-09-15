# syntax=docker/dockerfile:1
FROM python:3.11

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY rule_extractor/requirements.txt ./rule_extractor/requirements.txt
RUN pip install --no-cache-dir -r rule_extractor/requirements.txt

COPY rule_extractor ./rule_extractor

ENV PORT=8080
EXPOSE 8080
CMD ["uvicorn", "rule_extractor.app:app", "--host", "0.0.0.0", "--port", "8080"]