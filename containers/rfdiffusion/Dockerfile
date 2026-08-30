# RFdiffusion modernized stack for sm_89/sm_90 (4090/5090/L40S/H100).
#
# Upstream Dockerfile pins cuda 11.6.2 / py3.9 / torch 1.12.1+cu116, which
# fails on sm_89 with nvrtc 'invalid value for --gpu-architecture' (issue
# #289). We depart from upstream with the modernized-but-pinned stack
# validated against 4090 community RFdiffusion forks. The pinned
# pytorch/cuda/dgl combination is the supported runtime baseline.
#
# Weights are NOT baked into the image. They live on the campaign network
# volume at /workspace/software/weights/rfdiffusion (~5.3 GB total). Pull
# Complex_base_ckpt.pt for PPI / binder design (the default for this build).

FROM nvcr.io/nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Pin RFdiffusion to current stable main HEAD; replace before paid launch
# after re-resolving against github.com/RosettaCommons/RFdiffusion.
ARG RFDIFFUSION_REPO_URL=https://github.com/RosettaCommons/RFdiffusion.git
ARG RFDIFFUSION_REF=5606075d45bd23bc88451935a73c63ddcc3ca4d8
ARG RFDIFFUSION_INSTALL_PREFIX=/opt/rfdiffusion

# Base OS deps. `git` is required so the bridge gate
# (image_capabilities=[git]) passes; build deps are needed for SE3Transformer
# and the dgl 2.0.0+cu121 wheel install.
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    build-essential \
    python3.10 \
    python3.10-dev \
    python3.10-distutils \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Make python3.10 the default python/pip.
RUN ln -sf /usr/bin/python3.10 /usr/bin/python \
    && ln -sf /usr/bin/python3.10 /usr/bin/python3 \
    && python -m pip install --upgrade pip setuptools wheel

# PyTorch 2.1.2 + cu121 — cu121 nvrtc knows sm_89 / sm_90.
RUN pip install \
    torch==2.1.2+cu121 \
    torchvision==0.16.2+cu121 \
    torchaudio==2.1.2+cu121 \
    --extra-index-url https://download.pytorch.org/whl/cu121

# DGL 2.0.0 + cu121 (replaces upstream dgl==1.0.2+cu116).
RUN pip install dgl==2.0.0+cu121 \
    --extra-index-url https://data.dgl.ai/wheels/cu121/repo.html

# Core scientific stack and RFdiffusion deps. numpy is pinned <2 so torch
# 2.1.2 wheels don't ABI-break against numpy 2.x.
RUN pip install \
    "numpy<2" \
    "scipy" \
    "biopython" \
    "e3nn==0.5.1" \
    "hydra-core==1.3.2" \
    "wandb" \
    "pynvml" \
    "dllogger @ git+https://github.com/NVIDIA/dllogger.git" \
    "decorator" \
    "pyrsistent" \
    "icecream" \
    "omegaconf" \
    "opt_einsum"

# RFdiffusion source + SE3Transformer submodule.
RUN mkdir -p "${RFDIFFUSION_INSTALL_PREFIX}" \
    && git clone "${RFDIFFUSION_REPO_URL}" "${RFDIFFUSION_INSTALL_PREFIX}" \
    && git -C "${RFDIFFUSION_INSTALL_PREFIX}" checkout --detach "${RFDIFFUSION_REF}" \
    && pip install "${RFDIFFUSION_INSTALL_PREFIX}/env/SE3Transformer" \
    && pip install -e "${RFDIFFUSION_INSTALL_PREFIX}"

# Sanity check — torch sees CUDA at build time (no GPU needed for import).
RUN python -c "import torch, e3nn, dgl, hydra; print('torch', torch.__version__, 'dgl', dgl.__version__, 'e3nn', e3nn.__version__)"

ENV RFDIFFUSION_HOME=${RFDIFFUSION_INSTALL_PREFIX}
ENV PATH=${RFDIFFUSION_INSTALL_PREFIX}/scripts:${PATH}
WORKDIR /workspace

# Default entrypoint is a no-op; the bridge manifest's startup.commands
# drive the container via dockerStartCmd.
CMD ["bash"]
