
from __future__ import annotations

import argparse
import csv
import json
import random
import time
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader, Subset
from torchvision import datasets, models, transforms


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(r"C:\avdata\plantvillage\raw\color")
MODEL_DIR = PROJECT_ROOT / "ml" / "models"
EVALUATION_DIR = PROJECT_ROOT / "ml" / "evaluation"

SEED = 42
IMAGE_SIZE = 160
BATCH_SIZE = 16


def set_seed(seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)


def split_indices(targets: list[int], seed: int):
    """Create deterministic, stratified 70/15/15 splits."""
    rng = random.Random(seed)
    train_indices, val_indices, test_indices = [], [], []

    for class_id in sorted(set(targets)):
        indices = [
            i for i, target in enumerate(targets)
            if target == class_id
        ]
        rng.shuffle(indices)

        n = len(indices)
        n_train = int(n * 0.70)
        n_val = int(n * 0.15)

        train_indices.extend(indices[:n_train])
        val_indices.extend(indices[n_train:n_train + n_val])
        test_indices.extend(indices[n_train + n_val:])

    rng.shuffle(train_indices)
    rng.shuffle(val_indices)
    rng.shuffle(test_indices)

    return train_indices, val_indices, test_indices


def evaluate(model, loader, criterion, device):
    model.eval()
    total_loss = 0.0
    total = 0
    correct = 0
    class_correct = {}
    class_total = {}

    with torch.no_grad():
        for images, labels in loader:
            images = images.to(device)
            labels = labels.to(device)

            outputs = model(images)
            loss = criterion(outputs, labels)

            predictions = outputs.argmax(dim=1)
            total_loss += loss.item() * labels.size(0)
            total += labels.size(0)
            correct += (predictions == labels).sum().item()

            for label, prediction in zip(
                labels.cpu().tolist(),
                predictions.cpu().tolist(),
            ):
                class_total[label] = class_total.get(label, 0) + 1
                if label == prediction:
                    class_correct[label] = class_correct.get(label, 0) + 1

    accuracy = correct / total if total else 0.0
    average_loss = total_loss / total if total else 0.0

    return average_loss, accuracy, class_correct, class_total


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument(
        "--max-images-per-class",
        type=int,
        default=0,
        help="Use a limited sample per class for pipeline testing; 0 uses all images.",
    )
    parser.add_argument("--workers", type=int, default=0)
    args = parser.parse_args()

    if args.epochs < 1:
        raise ValueError("--epochs must be at least 1")

    if not DATA_DIR.is_dir():
        raise FileNotFoundError(f"Dataset directory not found: {DATA_DIR}")

    set_seed(SEED)
    torch.set_num_threads(max(1, min(4, torch.get_num_threads())))
    device = torch.device("cpu")

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    EVALUATION_DIR.mkdir(parents=True, exist_ok=True)

    # Validation/test images are never augmented.
    train_transform = transforms.Compose([
        transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(10),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225],
        ),
    ])

    eval_transform = transforms.Compose([
        transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225],
        ),
    ])

    # ImageFolder discovers labels from the actual class directory names.
    base_dataset = datasets.ImageFolder(DATA_DIR)
    class_names = base_dataset.classes

    # Optional small, deterministic sample to test the pipeline first.
    selected_indices = []
    if args.max_images_per_class > 0:
        rng = random.Random(SEED)
        for class_id in range(len(class_names)):
            indices = [
                i for i, (_, label) in enumerate(base_dataset.samples)
                if label == class_id
            ]
            rng.shuffle(indices)
            selected_indices.extend(
                indices[:args.max_images_per_class]
            )
        selected_indices.sort()
        targets = [base_dataset.targets[i] for i in selected_indices]
    else:
        selected_indices = list(range(len(base_dataset)))
        targets = list(base_dataset.targets)

    train_local, val_local, test_local = split_indices(targets, SEED)

    train_indices = [selected_indices[i] for i in train_local]
    val_indices = [selected_indices[i] for i in val_local]
    test_indices = [selected_indices[i] for i in test_local]

    # Separate dataset objects ensure augmentation is applied only to training.
    train_dataset = datasets.ImageFolder(DATA_DIR, transform=train_transform)
    eval_dataset = datasets.ImageFolder(DATA_DIR, transform=eval_transform)

    train_loader = DataLoader(
        Subset(train_dataset, train_indices),
        batch_size=BATCH_SIZE,
        shuffle=True,
        num_workers=args.workers,
    )
    val_loader = DataLoader(
        Subset(eval_dataset, val_indices),
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=args.workers,
    )
    test_loader = DataLoader(
        Subset(eval_dataset, test_indices),
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=args.workers,
    )

    print(f"Device: {device}")
    print(f"Classes: {len(class_names)}")
    print(f"Images used: {len(selected_indices)}")
    print(
        f"Split sizes — train: {len(train_indices)}, "
        f"validation: {len(val_indices)}, test: {len(test_indices)}"
    )
    print("Loading pretrained MobileNetV3-Small weights...")

    # First run may download official pretrained weights.
    model = models.mobilenet_v3_small(
        weights=models.MobileNet_V3_Small_Weights.DEFAULT
    )

    # Train only the new 38-class classification head initially.
    for parameter in model.parameters():
        parameter.requires_grad = False

    input_features = model.classifier[-1].in_features
    model.classifier[-1] = nn.Linear(input_features, len(class_names))
    model = model.to(device)

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(
        model.classifier[-1].parameters(),
        lr=0.001,
        weight_decay=0.0001,
    )

    best_val_accuracy = -1.0
    best_state = None
    history = []

    for epoch in range(args.epochs):
        start = time.time()
        model.train()
        running_loss = 0.0
        seen = 0

        for images, labels in train_loader:
            images = images.to(device)
            labels = labels.to(device)

            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            running_loss += loss.item() * labels.size(0)
            seen += labels.size(0)

        train_loss = running_loss / seen if seen else 0.0
        val_loss, val_accuracy, _, _ = evaluate(
            model, val_loader, criterion, device
        )

        record = {
            "epoch": epoch + 1,
            "train_loss": train_loss,
            "validation_loss": val_loss,
            "validation_accuracy": val_accuracy,
            "seconds": round(time.time() - start, 2),
        }
        history.append(record)
        print(json.dumps(record))

        if val_accuracy > best_val_accuracy:
            best_val_accuracy = val_accuracy
            best_state = {
                key: value.detach().cpu().clone()
                for key, value in model.state_dict().items()
            }

    if best_state is None:
        raise RuntimeError("Training did not produce a model checkpoint.")

    model.load_state_dict(best_state)

    # Evaluate the selected checkpoint once on the held-out test split.
    test_loss, test_accuracy, class_correct, class_total = evaluate(
        model, test_loader, criterion, device
    )

    macro_recall = sum(
        class_correct.get(i, 0) / class_total[i]
        for i in class_total
        if class_total[i] > 0
    ) / len(class_total)

    checkpoint_path = MODEL_DIR / "plant_disease_mobilenet_v3_small.pth"
    torch.save({
        "model_state_dict": model.state_dict(),
        "class_names": class_names,
        "image_size": IMAGE_SIZE,
        "architecture": "mobilenet_v3_small",
        "seed": SEED,
    }, checkpoint_path)

    with (MODEL_DIR / "plant_disease_classes.json").open(
        "w", encoding="utf-8"
    ) as file:
        json.dump(class_names, file, indent=2, ensure_ascii=False)

    with (EVALUATION_DIR / "plant_disease_training_history.csv").open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(file, fieldnames=list(history[0].keys()))
        writer.writeheader()
        writer.writerows(history)

    with (EVALUATION_DIR / "plant_disease_test_per_class.csv").open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.writer(file)
        writer.writerow(["class_name", "test_images", "correct", "recall"])
        for class_id, class_name in enumerate(class_names):
            count = class_total.get(class_id, 0)
            correct = class_correct.get(class_id, 0)
            recall = correct / count if count else 0.0
            writer.writerow([class_name, count, correct, round(recall, 6)])

    metrics = {
        "test_loss": test_loss,
        "test_accuracy": test_accuracy,
        "test_macro_recall": macro_recall,
        "best_validation_accuracy": best_val_accuracy,
        "test_images": len(test_indices),
        "classes": len(class_names),
        "checkpoint": str(checkpoint_path),
        "sampled_run": args.max_images_per_class > 0,
    }

    with (EVALUATION_DIR / "plant_disease_test_metrics.json").open(
        "w", encoding="utf-8"
    ) as file:
        json.dump(metrics, file, indent=2)

    print("\nTest metrics:")
    print(json.dumps(metrics, indent=2))
    print("Saved checkpoint:", checkpoint_path)


if __name__ == "__main__":
    main()
