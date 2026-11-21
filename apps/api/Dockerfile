FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml ./
COPY src/ ./src/

RUN python -m pip install --no-cache-dir .

USER 10001:10001

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "agentops_api.main:app", "--host", "0.0.0.0", "--port", "8000"]