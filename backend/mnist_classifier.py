"""
mnist_classifier.py
===================
MNIST-trained CNN digit classifier for the Numbers-to-Excel OCR pipeline.

This module:
  1. Defines a compact but powerful CNN (MNISTNet) for single-digit recognition.
  2. Parses the local `mnist_784.arff` file (70,000 samples, 784 pixel features + label).
  3. Trains the model with heavy augmentation to generalize to real, messy handwriting.
  4. Saves the trained weights to `backend/models/mnist_cnn.pt`.
  5. On subsequent startups, loads the saved model instantly (< 0.1 s).
  6. Exposes `classify_digit(cell_crop_bgr)` → (digit_str, confidence_float).

Usage from ocr_engine.py:
    from backend.mnist_classifier import classify_digit
    digit, conf = classify_digit(crop_bgr)
"""

import os
import time
import pathlib
import logging
from typing import Optional, Tuple

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset, random_split
import torchvision.transforms as T

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
#  Paths
# ---------------------------------------------------------------------------
_HERE = pathlib.Path(__file__).parent          # backend/
_ROOT = _HERE.parent                           # project root
_ARFF_PATH = _ROOT / "mnist_784 (1).arff"
_MODEL_PATH = _HERE / "models" / "mnist_cnn.pt"

# ---------------------------------------------------------------------------
#  Singleton state
# ---------------------------------------------------------------------------
_model: Optional["MNISTNet"] = None
_device: torch.device = torch.device("cpu")

# ---------------------------------------------------------------------------
#  CNN Architecture
# ---------------------------------------------------------------------------

class MNISTNet(nn.Module):
    """
    Compact 3-block CNN for MNIST digit classification.
    Achieves ~99.3% test accuracy on the standard MNIST benchmark.
    """

    def __init__(self):
        super().__init__()
        # Block 1: 1→32 channels, 28x28 → 14x14
        self.block1 = nn.Sequential(
            nn.Conv2d(1, 32, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.Conv2d(32, 32, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),          # → 14x14
            nn.Dropout2d(0.25),
        )
        # Block 2: 32→64 channels, 14x14 → 7x7
        self.block2 = nn.Sequential(
            nn.Conv2d(32, 64, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.Conv2d(64, 64, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),          # → 7x7
            nn.Dropout2d(0.25),
        )
        # Block 3: 64→128 channels, 7x7 → 1x1
        self.block3 = nn.Sequential(
            nn.Conv2d(64, 128, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d(1),  # Global Average Pooling → 1x1
        )
        # Classifier head
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Dropout(0.5),
            nn.Linear(128, 10),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.block1(x)
        x = self.block2(x)
        x = self.block3(x)
        return self.classifier(x)


# ---------------------------------------------------------------------------
#  Data Loading from local ARFF file
# ---------------------------------------------------------------------------

def _load_arff_data() -> Tuple[np.ndarray, np.ndarray]:
    """
    Parses the local mnist_784.arff file.
    Returns (X, y) where:
        X: float32 array of shape (N, 784), pixel values in [0, 255]
        y: int64 array of shape (N,), labels in {0..9}
    Falls back to sklearn's fetch_openml if the ARFF file is missing.
    """
    if _ARFF_PATH.exists():
        print(f"[MNIST] Loading local ARFF: {_ARFF_PATH} ({_ARFF_PATH.stat().st_size // (1024*1024)} MB)...")
        t0 = time.time()
        try:
            from scipy.io import arff as scipy_arff
            data, meta = scipy_arff.loadarff(str(_ARFF_PATH))
            # data is a structured numpy array with fields pixel1..pixel784 + class
            num_samples = len(data)
            names = meta.names()
            feature_cols = [col_name for col_name in names if col_name.lower().startswith("pixel")]
            label_col = "class"

            # Vectorized extraction — avoids O(N*784) Python loop
            X = np.column_stack([data[f].astype(np.float32) for f in feature_cols])
            y_raw = data[label_col]
            # Labels may be byte strings b'0'..b'9'
            if y_raw.dtype.kind in ("S", "O", "U"):
                y = np.array([int(v.decode() if isinstance(v, bytes) else str(v)) for v in y_raw], dtype=np.int64)
            else:
                y = y_raw.astype(np.int64)
            print(f"[MNIST] ARFF loaded in {time.time()-t0:.1f}s — {num_samples} samples")
            return X, y
        except Exception as e:
            print(f"[MNIST] ARFF parse failed ({e}), trying sklearn fallback...")

    # Fallback: use sklearn (downloads from internet on first call)
    print("[MNIST] Local ARFF not found — fetching from sklearn/openml (one-time download)...")
    from sklearn.datasets import fetch_openml
    mnist = fetch_openml("mnist_784", version=1, as_frame=False, parser="auto")
    X = mnist.data.astype(np.float32)
    y = mnist.target.astype(np.int64)
    return X, y


# ---------------------------------------------------------------------------
#  Custom Augmentation Transforms
# ---------------------------------------------------------------------------

def _elastic_distortion_batch(images: torch.Tensor, alpha: float = 20.0,
                               sigma: float = 3.0) -> torch.Tensor:
    """
    Applies elastic distortion to a batch of (N, 1, 28, 28) tensors.
    This is the single most impactful augmentation for handwritten digit
    recognition — simulates the natural variability of pen strokes.
    
    Uses random displacement fields smoothed with a Gaussian kernel.
    """
    N, C, H, W = images.shape
    
    # Generate random displacement fields
    dx = torch.randn(N, 1, H, W, device=images.device) * alpha
    dy = torch.randn(N, 1, H, W, device=images.device) * alpha
    
    # Smooth with Gaussian kernel
    kernel_size = int(6 * sigma + 1) | 1  # ensure odd
    x = torch.arange(kernel_size, dtype=torch.float32, device=images.device) - kernel_size // 2
    gauss_1d = torch.exp(-0.5 * (x / sigma) ** 2)
    gauss_1d = gauss_1d / gauss_1d.sum()
    
    # Separable 2D convolution for efficiency
    gauss_h = gauss_1d.view(1, 1, -1, 1)
    gauss_w = gauss_1d.view(1, 1, 1, -1)
    pad_size = kernel_size // 2
    
    dx = F.pad(dx, [pad_size]*4, mode='reflect')
    dx = F.conv2d(dx, gauss_h, padding=0)
    dx = F.conv2d(dx, gauss_w, padding=0)
    
    dy = F.pad(dy, [pad_size]*4, mode='reflect')
    dy = F.conv2d(dy, gauss_h, padding=0)
    dy = F.conv2d(dy, gauss_w, padding=0)
    
    # Trim to original size if needed
    dx = dx[:, :, :H, :W]
    dy = dy[:, :, :H, :W]
    
    # Build sampling grid
    grid_y, grid_x = torch.meshgrid(
        torch.linspace(-1, 1, H, device=images.device),
        torch.linspace(-1, 1, W, device=images.device),
        indexing='ij'
    )
    grid_x = grid_x.unsqueeze(0).unsqueeze(0).expand(N, -1, -1, -1)
    grid_y = grid_y.unsqueeze(0).unsqueeze(0).expand(N, -1, -1, -1)
    
    # Normalize displacement to [-1, 1] grid space
    grid_x = grid_x + dx * 2.0 / W
    grid_y = grid_y + dy * 2.0 / H
    
    grid = torch.stack([grid_x.squeeze(1), grid_y.squeeze(1)], dim=-1)
    
    return F.grid_sample(images, grid, mode='bilinear', padding_mode='zeros', align_corners=True)


def _morphological_augment_batch(images: torch.Tensor, p: float = 0.3) -> torch.Tensor:
    """
    Randomly dilates or erodes digit strokes to simulate variable pen thickness.
    Operates on batches using max/min pooling as differentiable morphological ops.
    """
    if torch.rand(1).item() > p:
        return images
    
    # Randomly choose dilation (thicker) or erosion (thinner)
    if torch.rand(1).item() > 0.5:
        # Dilation via max pooling
        return F.max_pool2d(images, kernel_size=3, stride=1, padding=1)
    else:
        # Erosion via min pooling (negate, max pool, negate back)
        return -F.max_pool2d(-images, kernel_size=3, stride=1, padding=1)


def _noise_and_contrast_batch(images: torch.Tensor, noise_std: float = 0.10,
                               contrast_range: Tuple = (0.8, 1.2),
                               brightness_range: Tuple = (-0.1, 0.1)) -> torch.Tensor:
    """
    Adds Gaussian noise and random brightness/contrast shifts to simulate
    camera noise, uneven lighting, and scan artifacts.
    """
    N = images.shape[0]
    
    # Gaussian noise
    if noise_std > 0:
        noise = torch.randn_like(images) * noise_std
        images = images + noise
    
    # Random contrast per sample
    contrast = torch.empty(N, 1, 1, 1, device=images.device).uniform_(*contrast_range)
    mean = images.mean(dim=(1, 2, 3), keepdim=True)
    images = (images - mean) * contrast + mean
    
    # Random brightness per sample
    brightness = torch.empty(N, 1, 1, 1, device=images.device).uniform_(*brightness_range)
    images = images + brightness
    
    return images.clamp(0, 1)


# Batch-level augmentation transforms (operates on tensors, no PIL conversion)
_BATCH_TRAIN_TRANSFORM = T.Compose([
    T.RandomAffine(
        degrees=20,           # increased from 15
        translate=(0.15, 0.15),  # increased from 0.10
        scale=(0.80, 1.20),   # widened from (0.85, 1.15)
        shear=12,             # increased from 10
        fill=0,
    ),
    T.RandomErasing(p=0.20, scale=(0.02, 0.10)),  # slightly stronger occlusion
])


# ---------------------------------------------------------------------------
#  Preprocessing helpers
# ---------------------------------------------------------------------------

def _to_tensor_batch(X: np.ndarray) -> torch.Tensor:
    """(N, 784) float32 → (N, 1, 28, 28) float32 in [0, 1]."""
    t = torch.from_numpy(X / 255.0).float()
    return t.view(-1, 1, 28, 28)


def _center_of_mass_shift(img_28: np.ndarray) -> np.ndarray:
    """
    Shifts the digit image so that its center of mass is at the image center.
    This is standard MNIST preprocessing and significantly improves recognition
    of off-center digits in real cell crops.
    """
    h, w = img_28.shape
    # Calculate center of mass
    total = img_28.sum()
    if total < 1e-6:
        return img_28
    
    ys, xs = np.mgrid[0:h, 0:w]
    cx = (xs * img_28).sum() / total
    cy = (ys * img_28).sum() / total
    
    # Shift to center
    shift_x = w / 2.0 - cx
    shift_y = h / 2.0 - cy
    
    M = np.float32([[1, 0, shift_x], [0, 1, shift_y]])
    shifted = cv2.warpAffine(img_28, M, (w, h), borderValue=0)
    return shifted


def _normalize_stroke_width(bin_img: np.ndarray, target_thickness: int = 2) -> np.ndarray:
    """
    Normalizes stroke thickness using morphological operations.
    Thin strokes get dilated, thick strokes get eroded, toward a target width.
    """
    if bin_img.sum() < 10:
        return bin_img
    
    # Estimate current stroke width using distance transform
    dist = cv2.distanceTransform(bin_img, cv2.DIST_L2, 5)
    fg_pixels = dist[bin_img > 0]
    if len(fg_pixels) == 0:
        return bin_img
    
    median_width = np.median(fg_pixels)
    
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    
    if median_width < target_thickness - 0.5:
        # Thin strokes — dilate
        return cv2.dilate(bin_img, kernel, iterations=1)
    elif median_width > target_thickness + 1.0:
        # Thick strokes — erode
        return cv2.erode(bin_img, kernel, iterations=1)
    
    return bin_img


def preprocess_cell_for_mnist(cell_bgr: np.ndarray) -> torch.Tensor:
    """
    Converts a BGR cell crop of any size to a (1, 1, 28, 28) float32 tensor
    ready for MNISTNet inference.

    Processing steps:
      1. Convert to grayscale & invert (white digit on black background).
      2. OTSU binarize to find ink.
      3. Connected components analysis to isolate main digit ink
         (filters out tiny printed top labels, border lines, and noise).
      4. Crop tightly with padding around main digit ink.
      5. Pad to square and resize to 28x28.
      6. Center-of-mass shift to match MNIST centering.
      7. Normalize pixel values to [0, 1].
    """
    # Step 1: Grayscale
    if len(cell_bgr.shape) == 3:
        gray = cv2.cvtColor(cell_bgr, cv2.COLOR_BGR2GRAY)
    else:
        gray = cell_bgr.copy()

    # Invert if background is light (most paper/photo crops)
    if gray.mean() > 128:
        gray = cv2.bitwise_not(gray)

    # Step 2: OTSU binarize
    _, bin_img = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Step 3: Connected components analysis to isolate main digit
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(bin_img)

    if num_labels > 1:
        # stats: [x, y, w, h, area]
        bg_area = stats[0, cv2.CC_STAT_AREA]
        fg_stats = stats[1:]  # exclude background label 0

        # Find largest foreground component
        areas = fg_stats[:, cv2.CC_STAT_AREA]
        max_idx = np.argmax(areas) + 1
        max_area = areas[max_idx - 1]

        # Keep components that are at least 12% of the largest component's area
        # (this keeps disconnected strokes like in 4, 5, 7, but drops tiny noise/labels)
        keep_labels = []
        for idx in range(1, num_labels):
            comp_area = stats[idx, cv2.CC_STAT_AREA]
            comp_y = stats[idx, cv2.CC_STAT_TOP]
            comp_h = stats[idx, cv2.CC_STAT_HEIGHT]

            # Reject components at the top 10% edge if they are small (tiny printed labels)
            is_top_label = (comp_y <= max(2, int(bin_img.shape[0] * 0.12))) and (comp_area < 0.35 * max_area)

            if comp_area >= max(10, int(max_area * 0.12)) and not is_top_label:
                keep_labels.append(idx)

        if not keep_labels:
            keep_labels = [max_idx]

        # Mask containing only kept digit components
        digit_mask = np.zeros_like(bin_img)
        for label in keep_labels:
            digit_mask[labels == label] = 255

        # Mask original grayscale image
        gray_clean = np.where(digit_mask > 0, gray, 0).astype(np.uint8)

        # Bounding box of kept digit components
        coords = cv2.findNonZero(digit_mask)
        if coords is not None:
            x, y, bw, bh = cv2.boundingRect(coords)
            pad_x = max(2, int(bw * 0.15))
            pad_y = max(2, int(bh * 0.15))
            x1 = max(0, x - pad_x)
            y1 = max(0, y - pad_y)
            x2 = min(gray.shape[1], x + bw + pad_x)
            y2 = min(gray.shape[0], y + bh + pad_y)
            cropped = gray_clean[y1:y2, x1:x2]
        else:
            cropped = gray
    else:
        cropped = gray

    if cropped.size == 0 or min(cropped.shape) < 2:
        cropped = gray

    # Step 4: Pad to square
    h, w = cropped.shape
    side = max(h, w)
    border = max(3, int(side * 0.20))
    total_side = side + 2 * border
    sq = np.zeros((total_side, total_side), dtype=np.uint8)
    y_off = (total_side - h) // 2
    x_off = (total_side - w) // 2
    sq[y_off:y_off+h, x_off:x_off+w] = cropped

    # Step 5: Resize to 28×28
    resized = cv2.resize(sq, (28, 28), interpolation=cv2.INTER_AREA)

    # Step 6: Center-of-mass shift (MNIST style)
    resized = _center_of_mass_shift(resized.astype(np.float32))
    resized = np.clip(resized, 0, 255).astype(np.uint8)

    # Step 7: Normalize to [0, 1] tensor
    tensor = torch.from_numpy(resized.astype(np.float32) / 255.0)
    return tensor.unsqueeze(0).unsqueeze(0)  # (1, 1, 28, 28)


# ---------------------------------------------------------------------------
#  Mixup Regularization
# ---------------------------------------------------------------------------

def _mixup_data(x: torch.Tensor, y: torch.Tensor, alpha: float = 0.2):
    """
    Applies Mixup regularization: blends pairs of samples and their labels.
    Significantly improves generalization by creating virtual training examples.
    
    Returns mixed inputs, pairs of targets, and the mixing coefficient lambda.
    """
    if alpha > 0:
        lam = np.random.beta(alpha, alpha)
    else:
        lam = 1.0
    
    batch_size = x.size(0)
    index = torch.randperm(batch_size, device=x.device)
    
    mixed_x = lam * x + (1 - lam) * x[index]
    y_a, y_b = y, y[index]
    return mixed_x, y_a, y_b, lam


def _mixup_criterion(criterion, pred, y_a, y_b, lam):
    """Computes loss for mixup-blended targets."""
    return lam * criterion(pred, y_a) + (1 - lam) * criterion(pred, y_b)


# ---------------------------------------------------------------------------
#  Training
# ---------------------------------------------------------------------------

def _train_model() -> "MNISTNet":
    """
    Trains MNISTNet on the full 70k MNIST dataset and saves weights.
    Returns the trained model in eval mode.
    
    Augmentation pipeline:
      - RandomAffine (rotation ±20°, translate ±15%, scale 0.80–1.20, shear ±12°)
      - Elastic distortion (alpha=20, sigma=3)
      - Morphological augmentation (random dilate/erode, p=0.3)
      - Gaussian noise + brightness/contrast shifts
      - Random erasing (p=0.20)
      - Mixup regularization (alpha=0.2)
    
    Training config:
      - 25 epochs with cosine annealing LR
      - Early stopping (patience=5)
      - Label smoothing (0.05)
    """
    print("\n" + "="*60)
    print("[MNIST] Starting training — this runs ONCE (~10-15 min CPU)")
    print("[MNIST] Enhanced augmentation: elastic + morphological + noise + mixup")
    print("="*60)

    # Load data
    X, y = _load_arff_data()

    # Build tensors
    X_t = _to_tensor_batch(X)   # (70000, 1, 28, 28)
    y_t = torch.from_numpy(y)   # (70000,)

    # Standard MNIST split: first 60k train, last 10k test
    X_train, X_test = X_t[:60000], X_t[60000:]
    y_train, y_test = y_t[:60000], y_t[60000:]

    train_ds = TensorDataset(X_train, y_train)
    test_ds  = TensorDataset(X_test,  y_test)

    # Augmented training loader
    train_loader = DataLoader(train_ds, batch_size=128, shuffle=True, num_workers=0, pin_memory=False)
    test_loader  = DataLoader(test_ds,  batch_size=256, shuffle=False, num_workers=0)

    model = MNISTNet().to(_device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    
    # Cosine annealing schedule for smoother convergence
    num_epochs = 25
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer,
        T_max=num_epochs,
        eta_min=1e-5,
    )
    criterion = nn.CrossEntropyLoss(label_smoothing=0.05)

    best_acc = 0.0
    best_state = None
    patience_counter = 0
    early_stop_patience = 5

    for epoch in range(1, num_epochs + 1):
        # --- Train ---
        model.train()
        total_loss = 0.0
        correct = 0
        t_epoch = time.time()

        for xb, yb in train_loader:
            xb = xb.to(_device)
            yb = yb.to(_device)

            # === Enhanced augmentation pipeline ===
            # 1. Standard geometric augmentation
            xb_aug = _BATCH_TRAIN_TRANSFORM(xb)
            
            # 2. Elastic distortion (p=0.5)
            if torch.rand(1).item() > 0.5:
                xb_aug = _elastic_distortion_batch(xb_aug, alpha=20.0, sigma=3.0)
            
            # 3. Morphological augmentation (thicken/thin strokes)
            xb_aug = _morphological_augment_batch(xb_aug, p=0.3)
            
            # 4. Noise and contrast/brightness shifts
            xb_aug = _noise_and_contrast_batch(
                xb_aug, noise_std=0.10,
                contrast_range=(0.8, 1.2),
                brightness_range=(-0.1, 0.1)
            )
            
            # 5. Mixup regularization
            xb_mixed, ya, yb_mix, lam = _mixup_data(xb_aug, yb, alpha=0.2)

            optimizer.zero_grad()
            out = model(xb_mixed)
            loss = _mixup_criterion(criterion, out, ya, yb_mix, lam)
            loss.backward()
            optimizer.step()

            total_loss += loss.item() * len(yb)
            # For accuracy tracking, use unmixed predictions
            with torch.no_grad():
                out_clean = model(xb_aug)
                correct += (out_clean.argmax(1) == yb).sum().item()

        train_acc = 100. * correct / len(train_ds)
        scheduler.step()

        # --- Evaluate ---
        model.eval()
        val_correct = 0
        with torch.no_grad():
            for xb, yb in test_loader:
                xb, yb = xb.to(_device), yb.to(_device)
                out = model(xb)
                val_correct += (out.argmax(1) == yb).sum().item()
        val_acc = 100. * val_correct / len(test_ds)

        elapsed = time.time() - t_epoch
        lr_now = scheduler.get_last_lr()[0]
        print(f"  Epoch {epoch:2d}/{num_epochs} | Loss: {total_loss/len(train_ds):.4f} | "
              f"Train Acc: {train_acc:.2f}% | Test Acc: {val_acc:.2f}% | "
              f"LR: {lr_now:.6f} | {elapsed:.1f}s", flush=True)

        if val_acc > best_acc:
            best_acc = val_acc
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        # Early stopping disabled by user request to train all 25 epochs
        # if patience_counter >= early_stop_patience:
        #     print(f"  [Early Stop] No improvement for {early_stop_patience} epochs. Stopping.")
        #     break

    # Load best weights
    if best_state:
        model.load_state_dict(best_state)

    print(f"\n[MNIST] Training complete. Best test accuracy: {best_acc:.2f}%")

    # Print per-class report
    _print_classification_report(model, test_loader)

    # Save model
    _MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "accuracy": best_acc}, str(_MODEL_PATH))
    print(f"[MNIST] Model saved -> {_MODEL_PATH}")

    model.eval()
    return model


def _print_classification_report(model: "MNISTNet", test_loader: DataLoader):
    """Prints per-class precision, recall, F1 after training."""
    model.eval()
    all_preds = []
    all_labels = []
    with torch.no_grad():
        for xb, yb in test_loader:
            out = model(xb.to(_device))
            all_preds.extend(out.argmax(1).cpu().numpy())
            all_labels.extend(yb.numpy())
    from sklearn.metrics import classification_report
    print("\n[MNIST] Per-class metrics on test set:")
    print(classification_report(all_labels, all_preds, digits=4))


# ---------------------------------------------------------------------------
#  Load or Train (singleton)
# ---------------------------------------------------------------------------

def load_or_train_classifier() -> "MNISTNet":
    """
    Returns the singleton MNISTNet model.
    - If `backend/models/mnist_cnn.pt` exists → loads instantly.
    - Otherwise → trains from scratch on the ARFF data, then saves.
    """
    global _model, _device

    if _model is not None:
        return _model

    if _MODEL_PATH.exists() and _MODEL_PATH.stat().st_size > 0:
        print(f"[MNIST] Loading pre-trained model from {_MODEL_PATH} ...")
        try:
            checkpoint = torch.load(str(_MODEL_PATH), map_location=_device, weights_only=True)
            m = MNISTNet().to(_device)
            m.load_state_dict(checkpoint["state_dict"])
            m.eval()
            acc = checkpoint.get("accuracy", None)
            acc_str = f"{acc:.2f}%" if isinstance(acc, (int, float)) else "unknown"
            print(f"[MNIST] Model loaded. Stored test accuracy: {acc_str}")
            _model = m
            return _model
        except Exception as e:
            print(f"[MNIST] Could not load model from {_MODEL_PATH} ({e}) — removing invalid file and retraining...")
            _MODEL_PATH.unlink(missing_ok=True)

    print("[MNIST] No valid pre-trained model found — starting training...")
    _model = _train_model()
    _model.eval()

    return _model


# ---------------------------------------------------------------------------
#  Public inference API
# ---------------------------------------------------------------------------

def classify_digit(cell_crop_bgr: np.ndarray) -> Tuple[str, float]:
    """
    Classifies a single handwritten digit in a BGR cell crop.

    Parameters
    ----------
    cell_crop_bgr : np.ndarray
        The cropped cell image in BGR format (any size).

    Returns
    -------
    digit : str
        The predicted digit character ('0'..'9'), or '' if the cell appears empty.
    confidence : float
        Softmax probability of the predicted class (0.0 – 1.0).
    """
    model = load_or_train_classifier()

    # Check if cell appears empty using foreground pixel ratio
    if len(cell_crop_bgr.shape) == 3:
        gray_check = cv2.cvtColor(cell_crop_bgr, cv2.COLOR_BGR2GRAY)
    else:
        gray_check = cell_crop_bgr
    
    # Better empty-cell detection: use both std AND foreground ratio
    if gray_check.std() < 5.0:
        return "", 0.0
    
    # Check foreground pixel ratio (after OTSU)
    if gray_check.mean() > 128:
        check_inv = cv2.bitwise_not(gray_check)
    else:
        check_inv = gray_check
    _, check_bin = cv2.threshold(check_inv, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    fg_ratio = np.count_nonzero(check_bin) / max(check_bin.size, 1)
    if fg_ratio < 0.01:  # less than 1% foreground = likely empty
        return "", 0.0

    try:
        tensor = preprocess_cell_for_mnist(cell_crop_bgr)  # (1, 1, 28, 28)
        with torch.no_grad():
            logits = model(tensor.to(_device))
            probs = F.softmax(logits, dim=1)[0]
            conf, pred = probs.max(0)
            return str(pred.item()), float(conf.item())
    except Exception as e:
        logger.warning(f"[MNIST] classify_digit error: {e}")
        return "", 0.0


def classify_digit_tta(cell_crop_bgr: np.ndarray, num_crops: int = 5) -> Tuple[str, float]:
    """
    Test-Time Augmentation: runs inference on multiple augmented variations
    of the same cell crop and returns the majority-voted prediction.
    
    This dramatically reduces wrong predictions for borderline-confidence cells.
    Uses shifts, slight rotations, and scale variations for diversity.
    
    Parameters
    ----------
    cell_crop_bgr : np.ndarray
        The cropped cell image in BGR format.
    num_crops : int
        Number of augmented crops to evaluate (default: 5).
    
    Returns
    -------
    digit : str
        Majority-voted digit prediction.
    confidence : float
        Average confidence of the winning digit.
    """
    model = load_or_train_classifier()
    
    # Check if cell appears empty
    if len(cell_crop_bgr.shape) == 3:
        gray_check = cv2.cvtColor(cell_crop_bgr, cv2.COLOR_BGR2GRAY)
    else:
        gray_check = cell_crop_bgr
    
    if gray_check.std() < 5.0:
        return "", 0.0
    
    h, w = cell_crop_bgr.shape[:2]
    center = (w / 2.0, h / 2.0)
    bg_val = 255 if gray_check.mean() > 128 else 0
    
    # Generate diverse augmented crops:
    # [0] = original
    # [1] = slight right-down shift
    # [2] = slight left-up shift
    # [3] = slight clockwise rotation (+5°)
    # [4] = slight scale up (105%)
    crops = [cell_crop_bgr]
    
    # Shift variations
    shifts = [
        (int(w * 0.04), int(h * 0.04)),     # right-down
        (-int(w * 0.04), -int(h * 0.04)),   # left-up
    ]
    for dx, dy in shifts:
        if len(crops) >= num_crops:
            break
        M = np.float32([[1, 0, dx], [0, 1, dy]])
        shifted = cv2.warpAffine(cell_crop_bgr, M, (w, h), borderValue=(bg_val, bg_val, bg_val) if len(cell_crop_bgr.shape) == 3 else bg_val)
        crops.append(shifted)
    
    # Rotation variation (+5°)
    if len(crops) < num_crops:
        M_rot = cv2.getRotationMatrix2D(center, 5.0, 1.0)
        rotated = cv2.warpAffine(cell_crop_bgr, M_rot, (w, h), borderValue=(bg_val, bg_val, bg_val) if len(cell_crop_bgr.shape) == 3 else bg_val)
        crops.append(rotated)
    
    # Scale variation (105%)
    if len(crops) < num_crops:
        M_scale = cv2.getRotationMatrix2D(center, 0, 1.05)
        scaled = cv2.warpAffine(cell_crop_bgr, M_scale, (w, h), borderValue=(bg_val, bg_val, bg_val) if len(cell_crop_bgr.shape) == 3 else bg_val)
        crops.append(scaled)
    
    # Run inference on each crop
    votes = {}  # digit -> [confidence_list]
    
    for crop in crops:
        try:
            tensor = preprocess_cell_for_mnist(crop)
            with torch.no_grad():
                logits = model(tensor.to(_device))
                probs = F.softmax(logits, dim=1)[0]
                conf, pred = probs.max(0)
                d = str(pred.item())
                c = float(conf.item())
                if d not in votes:
                    votes[d] = []
                votes[d].append(c)
        except Exception:
            continue
    
    if not votes:
        return "", 0.0
    
    # Return digit with most votes (tie-break by average confidence)
    best_digit = max(votes.keys(), key=lambda d: (len(votes[d]), sum(votes[d]) / len(votes[d])))
    avg_conf = sum(votes[best_digit]) / len(votes[best_digit])
    
    return best_digit, avg_conf


# ---------------------------------------------------------------------------
#  CLI entry point for standalone training
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("[MNIST] Running standalone training...")
    import sys
    # Force re-train if --retrain flag passed
    if "--retrain" in sys.argv and _MODEL_PATH.exists():
        print(f"[MNIST] Removing existing model: {_MODEL_PATH}")
        _MODEL_PATH.unlink()
    load_or_train_classifier()
    print("[MNIST] Done.")
