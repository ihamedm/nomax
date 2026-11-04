# Laya is kept in its own image so the API and worker never install PyTorch.
# The model is downloaded on first start and cached in /data/huggingface.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=180 \
    PIP_RETRIES=10 \
    HF_HOME=/data/huggingface \
    LAYA_HOST=0.0.0.0 \
    LAYA_PORT=8000 \
    LAYA_DEVICE=cpu \
    LAYA_PRELOAD=1 \
    LAYA_MODELS=multilingual \
    LAYA_DEFAULT_MODEL=multilingual \
    LAYA_MAX_LOADED=1 \
    LAYA_THREADS=2 \
    LAYA_IDLE_UNLOAD_SECONDS=0

# CPU-only torch keeps the optional model image much smaller than the default
# Linux wheel, which bundles CUDA. Pinning transformers avoids a future major
# release silently changing Laya's checkpoint loading path.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --index-url https://download.pytorch.org/whl/cpu torch \
    && pip install "laya[serve]==0.4.21" "transformers==4.57.1" "numpy<2"

RUN mkdir -p /data/huggingface
VOLUME ["/data/huggingface"]

EXPOSE 8000

CMD ["laya-serve"]
