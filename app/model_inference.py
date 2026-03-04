from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class InferenceOutput:
    model: str
    ai_probability: Optional[float]  # 0..1 или None
    detail: str


def run_frame_dummy(frame_paths: List[Path]) -> InferenceOutput:
    return InferenceOutput(
        model="frame_dummy",
        ai_probability=None,
        detail=f"dummy model, frames_seen={len(frame_paths)}",
    )


# ===== Шаг 3: PyTorch EfficientNet-B0 (инфраструктура) =====
_torch_model = None
_torch_device = "cpu"


def _load_efficientnet_b0():
    """
    Загружает базовую EfficientNet-B0 и подменяет классификатор на 2 класса.
    Голова НЕ обучена — это только инфраструктура.
    """
    global _torch_model, _torch_device
    if _torch_model is not None:
        return _torch_model

    import torch  # type: ignore
    from torchvision import models  # type: ignore

    _torch_device = "cpu"

    # Базовые веса ImageNet для фичей
    model = models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.DEFAULT)

    # Меняем классификатор на 2 класса
    in_features = model.classifier[1].in_features
    model.classifier[1] = torch.nn.Linear(in_features, 2)

    model.eval()
    model.to(_torch_device)

    _torch_model = model
    return _torch_model


def run_pytorch_efficientnet_b0(frame_paths: List[Path]) -> InferenceOutput:
    if not frame_paths:
        return InferenceOutput(
            model="pytorch_efficientnet_b0",
            ai_probability=None,
            detail="no frames to run inference",
        )

    try:
        import torch  # type: ignore
        from PIL import Image  # type: ignore
        from torchvision import transforms  # type: ignore
    except Exception as e:
        return InferenceOutput(
            model="pytorch_efficientnet_b0",
            ai_probability=None,
            detail=f"missing deps: {e}",
        )

    model = _load_efficientnet_b0()

    preprocess = transforms.Compose(
        [
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ]
    )

    # Не грузим больше 32 кадров (и так у тебя 32 по умолчанию)
    selected = frame_paths[:32]

    batch = []
    used = 0
    for p in selected:
        try:
            img = Image.open(p).convert("RGB")
            batch.append(preprocess(img))
            used += 1
        except Exception:
            continue

    if used == 0:
        return InferenceOutput(
            model="pytorch_efficientnet_b0",
            ai_probability=None,
            detail="all frames unreadable for PIL",
        )

    x = torch.stack(batch, dim=0)  # [N,3,224,224]

    with torch.no_grad():
        logits = model(x)  # [N,2]
        probs = torch.softmax(logits, dim=1)[:, 1]  # probability of class=1
        ai_prob = float(probs.mean().item())

    return InferenceOutput(
        model="pytorch_efficientnet_b0",
        ai_probability=ai_prob,
        detail=f"pytorch ok, frames_used={used}, note: head not trained yet",
    )