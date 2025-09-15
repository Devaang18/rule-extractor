.PHONY: venv install run build

venv:
	python3.11 -m venv .venv
	. .venv/bin/activate && pip install -U pip

install:
	. .venv/bin/activate && pip install -r rule_extractor/requirements.txt

run:
	. .venv/bin/activate && uvicorn rule_extractor.app:app --reload --env-file .env

build:
	docker build -t rule-extractor:local .
