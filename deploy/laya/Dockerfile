# Laya is kept in its own image so the API and worker never install PyTorch.
# Built from the upstream self-hosted source (github.com/NandhaKishorM/laya) at
# a pinned release instead of the published wheel, so this deployment runs its
# own copy of the decision engine. The model is downloaded on first start and
# cached in /data/huggingface.
FROM python:3.12-slim

ARG LAYA_VERSION=v0.4.35
ARG TORCH_VERSION=2.14.0

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

# CPU-only torch keeps the image much smaller than the default Linux wheel,
# which bundles CUDA. Laya's own dependencies (transformers 5.x, torch 2.14)
# are resolved by the source install below.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install "torch==${TORCH_VERSION}" --index-url https://download.pytorch.org/whl/cpu \
    && pip install "laya[serve] @ https://github.com/NandhaKishorM/laya/archive/refs/tags/${LAYA_VERSION}.tar.gz"

RUN mkdir -p /data/huggingface
VOLUME ["/data/huggingface"]

EXPOSE 8000

CMD ["laya-serve"]
