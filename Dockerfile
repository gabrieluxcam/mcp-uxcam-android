FROM python:3.12-slim

WORKDIR /app
COPY uxcam_server.py .

# install the official SDK from PyPI (no git needed)
RUN pip install --no-cache-dir "mcp[cli]"

CMD ["python", "/app/uxcam_server.py"]
