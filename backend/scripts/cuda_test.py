# Save this as gpu_test.py
import xgboost as xgb
import numpy as np
from time import time

# Create some synthetic data
n_samples = 10000
n_features = 20
X = np.random.rand(n_samples, n_features)
y = np.random.randint(0, 2, n_samples)

# Train with CPU
print("Training with CPU...")
start = time()
cpu_model = xgb.XGBClassifier(tree_method='exact', n_estimators=100)
cpu_model.fit(X, y)
cpu_time = time() - start
print(f"CPU training time: {cpu_time:.2f} seconds")

# Train with GPU
print("\nTraining with GPU...")
try:
    start = time()
    gpu_model = xgb.XGBClassifier(tree_method='hist', device='cuda', n_estimators=100)
    gpu_model.fit(X, y)
    gpu_time = time() - start
    print(f"GPU training time: {gpu_time:.2f} seconds")
    print(f"GPU speedup: {cpu_time/gpu_time:.2f}x faster than CPU")
except Exception as e:
    print(f"GPU training failed with error: {e}")
    print("CUDA is likely not available for XGBoost")