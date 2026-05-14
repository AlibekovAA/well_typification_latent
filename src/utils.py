from __future__ import annotations

import json
import pickle
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol, TypedDict, cast

import numpy as np
import torch
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from config import MODELS_DIR
from models.models import build_model


class ModelConfig(TypedDict):
    input_dim: int
    hidden_size: int
    num_layers: int
    kernel_size: int
    dilation_base: int
    dropout: float


class BestModelMeta(TypedDict):
    architecture: str


class ModelCheckpoint(TypedDict):
    architecture: str
    config: ModelConfig
    latent_dim: int
    model_state_dict: Mapping[str, object]


class EncodableModel(Protocol):
    def encode(self, x: torch.Tensor) -> torch.Tensor: ...

    def to(self, device: torch.device) -> EncodableModel: ...

    def eval(self) -> EncodableModel: ...

    def load_state_dict(self, state_dict: Mapping[str, object], strict: bool = True) -> object: ...


def get_device() -> torch.device:
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def load_trained_model(prefix: str, device: torch.device | None = None) -> tuple[EncodableModel, ModelCheckpoint]:
    if device is None:
        device = get_device()

    best_model_path = MODELS_DIR / prefix / "best_clustering_model.json"
    with open(best_model_path, encoding="utf-8") as f:
        best_meta = cast(BestModelMeta, json.load(f))
    best_arch = str(best_meta["architecture"]).lower()

    checkpoint_path = MODELS_DIR / prefix / best_arch / "model.pth"
    checkpoint = cast(
        ModelCheckpoint,
        torch.load(checkpoint_path, map_location=device, weights_only=False),
    )

    cfg = checkpoint["config"]

    model = cast(
        EncodableModel,
        build_model(
        arch_name=str(checkpoint["architecture"]),
        input_dim=int(cfg["input_dim"]),
        hidden_size=int(cfg["hidden_size"]),
        latent_dim=int(checkpoint["latent_dim"]),
        num_layers=int(cfg["num_layers"]),
        kernel_size=int(cfg["kernel_size"]),
        dilation_base=int(cfg["dilation_base"]),
        dropout=float(cfg["dropout"]),
        ),
    ).to(device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    return model, checkpoint


def _load_pickle(path: Path) -> object:
    if not path.exists():
        raise FileNotFoundError(f"Файл не найден: {path}")
    with open(path, "rb") as f:
        return pickle.load(f)


def load_scaler(prefix: str) -> StandardScaler:
    return cast(StandardScaler, _load_pickle(MODELS_DIR / prefix / "scaler.pkl"))


def load_kmeans(prefix: str) -> KMeans:
    return cast(KMeans, _load_pickle(MODELS_DIR / prefix / "kmeans.pkl"))


def load_latents_and_labels(prefix: str) -> tuple[np.ndarray, np.ndarray]:
    latents = np.load(MODELS_DIR / prefix / "latents.npy")
    labels = np.load(MODELS_DIR / prefix / "labels.npy")
    return latents, labels


def load_thresholds(prefix: str) -> dict[int, dict[str, float]]:
    raw = _load_pickle(MODELS_DIR / prefix / "thresholds.pkl")
    return cast(dict[int, dict[str, float]], raw)
