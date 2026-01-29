# Use Python 3.12 slim for smaller image size
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies needed for Tectonic
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Tectonic LaTeX compiler
# Tectonic is a modern, self-contained LaTeX engine written in Rust
# It's much smaller than full TeX Live (~50MB vs 1GB+)
# Detect architecture and download appropriate binary
RUN TECTONIC_VERSION=0.15.0 && \
    ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then \
        TECTONIC_ARCH="x86_64-unknown-linux-musl"; \
    elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then \
        TECTONIC_ARCH="aarch64-unknown-linux-musl"; \
    else \
        echo "Unsupported architecture: $ARCH" && exit 1; \
    fi && \
    curl -L "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40${TECTONIC_VERSION}/tectonic-${TECTONIC_VERSION}-${TECTONIC_ARCH}.tar.gz" \
    | tar -xz && \
    find . -name "tectonic" -type f -executable -exec mv {} /usr/local/bin/ \; && \
    chmod +x /usr/local/bin/tectonic && \
    rm -rf tectonic-* && \
    tectonic --version

# Copy dependency files
COPY pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Copy application code
COPY app.py ./

# Expose port
EXPOSE 8080

# Set environment variables
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Run the application
CMD ["python", "app.py"]

