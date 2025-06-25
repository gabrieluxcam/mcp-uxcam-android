FROM python:3.12-slim

WORKDIR /app
COPY uxcam_server.py .

# 1️⃣  install git (tiny, ~20 MB) so pip can pull from GitHub
RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

# 2️⃣  now grab the preview SDK straight from GitHub
RUN pip install --no-cache-dir "mcp-sdk @ git+https://github.com/gabrieluxcam/mcp-uxcam-android.git@main"

CMD ["python", "/app/uxcam_server.py"]
