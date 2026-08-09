FROM python:3.11-slim

WORKDIR /app

# Install system deps for aiosqlite
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./

RUN pip install --no-cache-dir \
    langgraph openai pydantic python-dotenv sqlmodel aiosqlite \
    fastapi httpx redis uvicorn

COPY . .

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
