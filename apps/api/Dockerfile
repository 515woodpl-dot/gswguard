FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app

COPY apps/api/requirements.txt /app/apps/api/requirements.txt
RUN pip install --no-cache-dir -r /app/apps/api/requirements.txt
COPY apps/api /app/apps/api
COPY packages /app/packages

RUN groupadd --gid 10001 yorguard \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin yorguard \
    && chown -R yorguard:yorguard /app
USER 10001:10001

EXPOSE 8000
CMD ["uvicorn", "apps.api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
