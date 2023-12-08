run:
	@echo "Starting Server..."
	python server.py

run-proxy:
	@echo "Starting Dev Proxy..."
	python dev_proxy.py

requirements:
	pipenv lock
	pipenv run pip freeze > requirements.txt

build:
	docker build -t firelink-backend:latest .

run-docker:
	docker run -e OC_TOKEN -e OC_SERVER -p 8000:8000 firelink-backend:latest
