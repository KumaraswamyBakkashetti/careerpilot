FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.21 /uv /usr/local/bin/uv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1
WORKDIR /app/backend
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY app ./app
COPY knowledge_data ./knowledge_data
RUN useradd --create-home --uid 10001 careerpilot && mkdir -p /app/private/resumes && chown -R careerpilot:careerpilot /app/private
USER careerpilot
ENV PATH="/app/backend/.venv/bin:$PATH"
EXPOSE 8000
CMD ["python", "-m", "app"]
