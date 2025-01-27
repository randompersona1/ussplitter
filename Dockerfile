FROM nvidia/cuda:12.1.0-base-ubuntu22.04
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Download and install model
ADD https://dl.fbaipublicfiles.com/demucs/hybrid_transformer/f7e0c4bc-ba3fe64a.th /app/models/hub/checkpoints/f7e0c4bc-ba3fe64a.th
ADD https://dl.fbaipublicfiles.com/demucs/hybrid_transformer/d12395a8-e57c48e6.th /app/models/hub/checkpoints/d12395a8-e57c48e6.th
ADD https://dl.fbaipublicfiles.com/demucs/hybrid_transformer/92cfc3b6-ef3bcb9c.th /app/models/hub/checkpoints/92cfc3b6-ef3bcb9c.th
ADD https://dl.fbaipublicfiles.com/demucs/hybrid_transformer/04573f0d-f3cf25b2.th /app/models/hub/checkpoints/04573f0d-f3cf25b2.th
ENV TORCH_HOME=/app/models

# Set working directory
WORKDIR /app

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
ADD src/ussplitter ./ussplitter
ADD .python-version .
ADD pyproject.toml .
ADD uv.lock .

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --only-group torch

EXPOSE 5000

# Run the application
# DO NOT TOUCH THE WORKERS. CODE IS NOT THREAD SAFE
CMD ["uv", "run", "--no-dev", "--group", "torch", "gunicorn", "-b", "0.0.0.0:5000", "-w", "1", "ussplitter.server:app"]