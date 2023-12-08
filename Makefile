run:
	@echo "Starting Server..."
	python server.py

run-proxy:
	@echo "Starting Dev Proxy..."
	python dev_proxy.py

requirements:
	pipenv lock
	pipenv run pip freeze > requirements.txt


