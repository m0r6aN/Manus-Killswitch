# PyTorch Version and CUDA availability.

import torch

print("PyTorch version:", torch.__version__)
print("CUDA available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("CUDA device name:", torch.cuda.get_device_name(0))
    print("CUDA capability:", torch.cuda.get_device_capability(0))
    print("PyTorch CUDA version:", torch.version.cuda)
    
# PyTorch version: 2.7.0.dev20250310+cu128
# CUDA available: True
# CUDA device name: NVIDIA RTX 3500 Ada Generation Laptop GPU
# CUDA capability: (8, 9)
# PyTorch CUDA version: 12.8