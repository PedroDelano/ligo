format:
	uv run isort src
	uv run black src
	uv run ruff check --fix src