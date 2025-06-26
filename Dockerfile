FROM python:3.12-slim

WORKDIR /app
COPY uxcam_server.py .

# Install the latest MCP SDK
RUN pip install --no-cache-dir --upgrade "mcp>=1.0.0"

CMD ["python", "/app/uxcam_server.py"]