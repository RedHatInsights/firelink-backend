run:
	@echo "Starting Server..."
	flask --app=server.py run --host=0.0.0.0 --port=5001

run-proxy:
	@echo "Starting Dev Proxy..."
	@command -v caddy >/dev/null 2>&1 || { echo >&2 "Caddy is not installed.  Aborting."; exit 1; }
	caddy run --config proxy/Caddyfile

requirements:
	pipenv lock
	pipenv run pip freeze > requirements.txt

build:
	docker build -t firelink-backend:latest .

run-docker:
	docker run -e OC_TOKEN -e OC_SERVER -p 8000:8000 firelink-backend:latest

test:
	python -m pytest tests/
