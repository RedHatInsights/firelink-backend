start-ui:
	@echo "Starting UI..."
	@cd firelink-ui && npm start

start-server:
	@echo "Starting Server..."
	python server.py

start-proxy:
	@echo "Starting Dev Proxy..."
	python dev_proxy.py

build:
	GIT_SHA=$$(git rev-parse --short=7 HEAD) && \
	podman build -t firelink:$$GIT_SHA .

.PHONY: build start-ui start-server start-proxy
