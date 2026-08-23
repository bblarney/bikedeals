# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# No build toolchain needed: every pin in requirements.txt publishes a
# manylinux cp312 wheel, asyncpg and pydantic-core included.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# alembic.ini and migrations/ ride along so `docker compose run api alembic
# upgrade head` works against the same image the API runs from.
COPY api/ ./api/
COPY scrapers/ ./scrapers/
COPY migrations/ ./migrations/
COPY alembic.ini .

RUN useradd --system --create-home --uid 10001 bikegrid
USER bikegrid

EXPOSE 8000

# --proxy-headers + --forwarded-allow-ips lets slowapi's get_remote_address see
# the real client IP from Caddy's X-Forwarded-For. Without them every request
# looks like it came from Caddy and the rate limiter throttles all users as one.
# Trusting "*" is safe here only because port 8000 is never published to the
# host: Caddy on the compose network is the sole thing that can reach it.
CMD ["uvicorn", "api.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
