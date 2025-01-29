FROM nvidia/cuda:12.1.0-base-ubuntu22.04
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app
ENV TORCH_HOME=/app/models
ENV TORCHAUDIO_USE_BACKEND_DISPATCHER=1

# We set the timezone because ffmpegs dependancy `tzdata` will otherwise prompt us to set it interactively
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    git \
    ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install python dependancies from uv
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=.python-version,target=.python-version \
    uv sync --frozen --no-install-project --link-mode=copy --only-group torch

# Copy all files
ADD src/ussplitter ./src/ussplitter
ADD .python-version .
ADD pyproject.toml .
ADD uv.lock .
ADD README.md .
ADD LICENSE .

EXPOSE 5000

# Run the application
# DO NOT TOUCH THE WORKERS. CODE IS NOT THREAD SAFE
CMD ["uv", "run", "--no-dev", "--group", "torch", "waitress-serve", "--listen", "0.0.0.0:5000", "--threads", "1", "ussplitter.server:app"]