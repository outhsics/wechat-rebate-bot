.PHONY: install run test

install:
	python3 -m venv .venv
	. .venv/bin/activate && pip install -r requirements.txt

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

test:
	pytest -q
