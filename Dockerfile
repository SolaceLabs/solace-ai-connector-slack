FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY . /app

# Build Solace Agent Mesh
# Create a non-root user
RUN \
	python3.11 -m pip install solace-agent-mesh && \
	python3.11 -m pip install --no-cache-dir . && \
	solace-agent-mesh build && \
	groupadd -r samapp && useradd -r -g samapp samapp && \
	chown -R samapp:samapp /app /tmp

# Switch to non-root user
USER samapp

# Default entry point
ENTRYPOINT ["solace-agent-mesh", "run"]