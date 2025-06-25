FROM python:3.12-slim
WORKDIR /app
COPY uxcam_server.py .
RUN pip install --no-cache-dir "mcp-sdk @ git+https://github.com/modelcontextprotocol/mcp-python-sdk.git@main"
CMD ["python","/app/uxcam_server.py"]
