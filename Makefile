format:
	uv run isort src
	uv run black src
	uv run ruff check --fix src

get-pachi:
	mkdir -p engines/pachi
	wget https://github.com/pasky/pachi/releases/download/pachi-12.86/pachi-12.86-linux-amd64-avx.zip -O blobs/pachi-engine.zip
	unzip -o blobs/pachi-engine.zip -d engines
	mv engines/Pachi-12.86/* engines/pachi/
	rm -rf engines/Pachi-12.86
