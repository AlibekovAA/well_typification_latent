from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any, cast

import numpy as np
import torch
from torch import nn

from config import MODEL_HYPERPARAMS, MODELS_DIR
from models.models import build_model


def get_device() -> torch.device:
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def load_trained_model(prefix: str, device: torch.device | None = None) -> tuple[nn.Module, dict[str, Any]]:
    if device is None:
        device = get_device()

    checkpoint: dict[str, Any] = torch.load(MODELS_DIR / prefix / "model.pth", map_location=device, weights_only=False)
    hp = MODEL_HYPERPARAMS
    model = build_model(
        arch_name=str(checkpoint["architecture"]),
        input_dim=int(hp["input_dim"]),
        hidden_size=int(hp["hidden_size"]),
        latent_dim=int(checkpoint["latent_dim"]),
        num_layers=int(hp["num_layers"]),
        kernel_size=int(hp["kernel_size"]),
        dilation_base=int(hp["dilation_base"]),
        dropout=float(hp["dropout"]),
    ).to(device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    return model, checkpoint


def _load_pickle(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Файл не найден: {path}")
    with open(path, "rb") as f:
        return pickle.load(f)


def load_scaler(prefix: str) -> Any:
    return _load_pickle(MODELS_DIR / prefix / "scaler.pkl")


def load_kmeans(prefix: str) -> Any:
    return _load_pickle(MODELS_DIR / prefix / "kmeans.pkl")


def load_latents_and_labels(prefix: str) -> tuple[np.ndarray, np.ndarray]:
    latents = np.load(MODELS_DIR / prefix / "latents.npy")
    labels = np.load(MODELS_DIR / prefix / "labels.npy")
    return latents, labels


def load_thresholds(prefix: str) -> dict[int, dict[str, float]]:
    raw = _load_pickle(MODELS_DIR / prefix / "thresholds.pkl")
    return cast(dict[int, dict[str, float]], raw)
