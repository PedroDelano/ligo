# LIGO

A libre Go website.

## Requirements

- Docker
- uv

## Running

```bash
docker run --rm -d -p 6379:6379 redis
uv run daphne -b 0.0.0.0 -p 8000 server.asgi:application
```