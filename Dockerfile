FROM python:3.10-slim-bullseye

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install build tools and base CLI
RUN pip install hatchling
RUN pip install cite-agent>=2.0.0

# Copy project files
COPY pyproject.toml .
COPY README.md .
COPY mcp_server.py .

# Install MCP dependencies
RUN pip install mcp httpx uvicorn starlette

# Environment variables
ENV PYTHONUNBUFFERED=1

# Run the server
CMD ["python", "mcp_server.py"]

