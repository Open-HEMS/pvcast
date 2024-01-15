FROM mcr.microsoft.com/devcontainers/python:3.12

LABEL Name=pvcast

COPY pyproject.toml poetry.lock ./

RUN pip install --upgrade pip  \
    && pip install --no-cache-dir poetry \
    && poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi
