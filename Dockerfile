# Use a Python image with uv pre-installed
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Install system dependencies if needed (none strictly required for these python deps usually, but git might be useful)
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# Install the project's dependencies using the lockfile and settings
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Add the project source and install it
# We copy specific files to avoid invalidating cache unnecessarily, though for this simple app '.' is often fine.
# But we should be selective to avoid copying unwanted local files like .git
COPY pyproject.toml uv.lock ./
COPY bob.py ./
COPY SYSTEM_PROMPT.md ./
COPY search_tool ./search_tool
COPY tools ./tools

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Create data directory for persistent storage
RUN mkdir -p /app/data

# Place the executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

# Reset the entrypoint, don't invoke `uv`
ENTRYPOINT []

# Run the application
CMD ["python", "bob.py"]
