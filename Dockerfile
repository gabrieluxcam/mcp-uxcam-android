FROM python:3.12-slim
WORKDIR /app
COPY uxcam_server.py .
RUN pip install mcp-sdk
CMD ["python","/app/uxcam_server.py"]
