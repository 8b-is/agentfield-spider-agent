FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py spider_server.py ./
COPY reasoners ./reasoners
COPY spider ./spider

EXPOSE 8005 11700

# Explicit STOPSIGNAL — docker defaults to SIGTERM but stating it lets
# operators (and future Dockerfile readers) know we rely on it. Python
# isn't PID 1 in some orchestrators; if you wrap with tini/dumb-init,
# they forward SIGTERM correctly.
STOPSIGNAL SIGTERM

CMD ["python", "main.py"]
