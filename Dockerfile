FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8100
ENV MCP_HOST=0.0.0.0
CMD ["python", "server.py"]
