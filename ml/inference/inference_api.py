
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn
from fastapi import FastAPI, File, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from torchvision import models, transforms

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agrovision.inference")

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = (
    PROJECT_ROOT
    / "ml"
    / "models"
    / "plant_disease_mobilenet_v3_small.pth"
)
CLASSES_PATH = (
    PROJECT_ROOT
    / "ml"
    / "models"
    / "plant_disease_classes.json"
)

IMAGE_SIZE = 160
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB

DEVICE = torch.device("cpu")

app = FastAPI(
    title="AgroVision Plant Disease Inference API",
    version="1.0.0",
    description=(
        "Plant disease image classification using a trained "
        "MobileNetV3-Small model."
    ),
)


def load_classes(path: Path) -> list[str]:
    """Load class names while preserving the training class order."""
    if not path.exists():
        raise FileNotFoundError(f"Class labels file not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        data: Any = json.load(file)

    if isinstance(data, list):
        classes = data

    elif isinstance(data, dict):
        # Support common class metadata formats.
        if isinstance(data.get("classes"), list):
            classes = data["classes"]

        elif isinstance(data.get("class_names"), list):
            classes = data["class_names"]

        elif isinstance(data.get("class_to_idx"), dict):
            mapping = data["class_to_idx"]
            classes = [
                name
                for name, index in sorted(
                    mapping.items(), key=lambda item: int(item[1])
                )
            ]

        elif all(isinstance(value, int) for value in data.values()):
            # Format: {"class_name": class_index}
            classes = [
                name
                for name, index in sorted(
                    data.items(), key=lambda item: item[1]
                )
            ]

        elif all(str(key).isdigit() for key in data):
            # Format: {"0": "class_name", "1": "class_name"}
            classes = [
                name
                for _, name in sorted(
                    data.items(), key=lambda item: int(item[0])
                )
            ]

        else:
            raise ValueError(
                "Unrecognized class-label JSON format. "
                "Inspect plant_disease_classes.json."
            )
    else:
        raise ValueError("Class-label JSON must contain a list or object.")

    if not classes or not all(isinstance(name, str) for name in classes):
        raise ValueError("Class labels must be a non-empty list of strings.")

    if len(set(classes)) != len(classes):
        raise ValueError("Duplicate class labels detected.")

    return classes


def build_model(number_of_classes: int) -> nn.Module:
    """Construct the same MobileNetV3-Small architecture used for training."""
    model = models.mobilenet_v3_small(weights=None)

    input_features = model.classifier[-1].in_features
    model.classifier[-1] = nn.Linear(
        input_features, number_of_classes
    )

    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model checkpoint not found: {MODEL_PATH}")

    checkpoint = torch.load(
        MODEL_PATH,
        map_location=DEVICE,
        weights_only=True,
    )

    # Support either a raw state_dict or a wrapped checkpoint.
    if isinstance(checkpoint, dict):
        if "model_state_dict" in checkpoint:
            state_dict = checkpoint["model_state_dict"]
        elif "state_dict" in checkpoint:
            state_dict = checkpoint["state_dict"]
        else:
            state_dict = checkpoint
    else:
        raise ValueError("Unsupported model checkpoint format.")

    # Handle checkpoints saved from DataParallel.
    if state_dict and all(
        key.startswith("module.") for key in state_dict
    ):
        state_dict = {
            key.removeprefix("module."): value
            for key, value in state_dict.items()
        }

    model.load_state_dict(state_dict, strict=True)
    model.to(DEVICE)
    model.eval()

    return model


# Keep preprocessing consistent with training.
# This assumes training used ImageNet normalization and 160x160 resizing.
preprocess = transforms.Compose(
    [
        transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225],
        ),
    ]
)

try:
    CLASS_NAMES = load_classes(CLASSES_PATH)
    model = build_model(len(CLASS_NAMES))
    logger.info(
        "Loaded model with %d classes on %s",
        len(CLASS_NAMES),
        DEVICE,
    )
except Exception:
    logger.exception("Failed to initialize plant disease model")
    raise


@app.get("/health")
def health_check() -> dict[str, Any]:
    return {
        "status": "healthy",
        "service": "plant-disease-inference",
        "device": str(DEVICE),
        "model_loaded": True,
        "classes": len(CLASS_NAMES),
    }


@app.get("/classes")
def get_classes() -> dict[str, Any]:
    return {
        "count": len(CLASS_NAMES),
        "classes": CLASS_NAMES,
    }


@app.post("/predict")
async def predict_plant_disease(
    file: UploadFile = File(...),
) -> dict[str, Any]:
    if file.content_type not in {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/bmp",
    }:
        raise HTTPException(
            status_code=415,
            detail="Upload a JPEG, PNG, WEBP, or BMP image.",
        )

    try:
        contents = await file.read(MAX_IMAGE_BYTES + 1)

        if not contents:
            raise HTTPException(status_code=400, detail="Image is empty.")

        if len(contents) > MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=413,
                detail="Image exceeds the 10 MB limit.",
            )

        from io import BytesIO

        try:
            with Image.open(BytesIO(contents)) as source:
                source.verify()

            with Image.open(BytesIO(contents)) as source:
                image = source.convert("RGB")
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            raise HTTPException(
                status_code=400,
                detail="The uploaded file is not a valid image.",
            )

        input_tensor = preprocess(image).unsqueeze(0).to(DEVICE)

        with torch.inference_mode():
            logits = model(input_tensor)
            probabilities = torch.softmax(logits, dim=1)[0]

        top_count = min(3, len(CLASS_NAMES))
        scores, indices = torch.topk(probabilities, k=top_count)

        predicted_index = int(indices[0].item())
        confidence = float(scores[0].item())

        return {
            "predicted_class": CLASS_NAMES[predicted_index],
            "confidence": round(confidence, 6),
            "confidence_percent": round(confidence * 100, 2),
            "top_predictions": [
                {
                    "class_name": CLASS_NAMES[int(index.item())],
                    "confidence": round(float(score.item()), 6),
                    "confidence_percent": round(
                        float(score.item()) * 100, 2
                    ),
                }
                for score, index in zip(scores, indices)
            ],
            "model": "MobileNetV3-Small",
            "dataset": "PlantVillage color images",
            "disclaimer": (
                "This is an AI prediction, not a confirmed diagnosis. "
                "Performance on real-world farm images may differ."
            ),
        }

    finally:
        await file.close()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8003,
    )