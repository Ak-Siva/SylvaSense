#!/usr/bin/env bash
set -e

python -m pip install --upgrade pip

echo "Installing CPU-only PyTorch..."

python -m pip install \
  --index-url https://download.pytorch.org/whl/cpu \
  torch==2.14.0+cpu \
  torchvision==0.29.0+cpu

echo "Installing backend dependencies..."

python -m pip install -r requirements.txt

echo "Installing DeepForest without replacing CPU PyTorch..."

python -m pip install --no-deps deepforest==2.1.0

echo "Checking installation..."

python -c "import torch; print('Torch:', torch.__version__); print('CUDA:', torch.cuda.is_available())"

python -c "import deepforest; print('DeepForest:', deepforest.__version__)"