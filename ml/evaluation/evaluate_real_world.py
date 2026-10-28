
"""
AgroVision real-world crop-health baseline evaluation.

Run from the ml directory:
python .\evaluation\evaluate_real_world.py --data .\data\crop_health\test

Dataset format:
test/<exact-model-class-name>/<image-file>

Use independently verified labels only.
This script does not modify the trained model or dataset.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

import torch
from torchvision import datasets, models, transforms

IMAGE_SIZE = 160
MEAN = (0.485, 0.456, 0.406)
STD = (0.229, 0.224, 0.225)
EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def read_classes(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))

    if isinstance(data, list):
        names = [str(x) for x in data]
    elif isinstance(data, dict):
        for key in ("classes", "class_names", "labels"):
            if isinstance(data.get(key), list):
                names = [str(x) for x in data[key]]
                break
        else:
            if data and all(str(k).isdigit() for k in data):
                names = [
                    str(data[k])
                    for k in sorted(data, key=lambda k: int(str(k)))
                ]
            elif data and all(isinstance(v, int) for v in data.values()):
                names = [
                    name for name, _ in sorted(
                        data.items(), key=lambda item: item[1]
                    )
                ]
            else:
                raise ValueError("Unrecognized class mapping JSON format.")
    else:
        raise ValueError("Class mapping must be a JSON list or object.")

    if not names or len(set(names)) != len(names):
        raise ValueError("Class mapping is empty or contains duplicates.")

    return names


def extract_state_dict(checkpoint):
    """Support common PyTorch checkpoint formats."""
    if not isinstance(checkpoint, dict):
        raise ValueError("Checkpoint must contain a state dictionary.")

    for key in ("model_state_dict", "state_dict", "model"):
        value = checkpoint.get(key)
        if isinstance(value, dict) and value:
            checkpoint = value
            break

    if not checkpoint or not all(
        isinstance(value, torch.Tensor)
        for value in checkpoint.values()
    ):
        raise ValueError(
            "Could not identify a model state dictionary in the checkpoint."
        )

    cleaned = {}
    for key, value in checkpoint.items():
        if key.startswith("module."):
            key = key[len("module."):]
        cleaned[key] = value

    return cleaned


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=Path("models/plant_disease_mobilenet_v3_small.pth"),
    )
    parser.add_argument(
        "--classes",
        type=Path,
        default=Path("models/plant_disease_classes.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation/real_world"),
    )
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()

    for path in (args.data, args.checkpoint, args.classes):
        if not path.exists():
            print(f"ERROR: path not found: {path.resolve()}", file=sys.stderr)
            return 2

    if args.batch_size < 1:
        print("ERROR: batch size must be at least 1.", file=sys.stderr)
        return 2

    try:
        from sklearn.metrics import (
            accuracy_score,
            classification_report,
            confusion_matrix,
            f1_score,
            precision_score,
            recall_score,
        )
    except ImportError:
        print(
            "Install scikit-learn in your ML venv:\n"
            "python -m pip install scikit-learn",
            file=sys.stderr,
        )
        return 2

    try:
        class_names = read_classes(args.classes)

        transform = transforms.Compose([
            transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
            transforms.ToTensor(),
            transforms.Normalize(MEAN, STD),
        ])

        dataset = datasets.ImageFolder(
            str(args.data),
            transform=transform,
            is_valid_file=lambda p: Path(p).suffix.lower() in EXTENSIONS,
        )

        if not dataset.samples:
            print(
                "ERROR: no supported images found in class subfolders.",
                file=sys.stderr,
            )
            return 2

        unknown = sorted(set(dataset.classes) - set(class_names))
        if unknown:
            print(f"ERROR: folders not present in model classes: {unknown}")
            return 2

        # Require nonempty, correctly named class folders.
        mapping = {name: i for i, name in enumerate(class_names)}
        dataset.samples = [
            (path, mapping[Path(path).parent.name])
            for path, _ in dataset.samples
        ]
        dataset.imgs = dataset.samples
        dataset.targets = [label for _, label in dataset.samples]
        dataset.classes = class_names
        dataset.class_to_idx = mapping

        present_classes = sorted({
            Path(path).parent.name for path, _ in dataset.samples
        })

        print(f"Images: {len(dataset)}")
        print(
            f"Verified classes represented: {len(present_classes)} "
            f"of {len(class_names)} model classes"
        )
        print(f"Device: {'CUDA' if torch.cuda.is_available() else 'CPU'}")

        loader = torch.utils.data.DataLoader(
            dataset,
            batch_size=args.batch_size,
            shuffle=False,
            num_workers=0,
        )

        # Rebuild the exact architecture used by the trained checkpoint.
        model = models.mobilenet_v3_small(weights=None)
        model.classifier[3] = torch.nn.Linear(
            model.classifier[3].in_features,
            len(class_names),
        )

        try:
            checkpoint = torch.load(
                args.checkpoint,
                map_location="cpu",
                weights_only=True,
            )
        except TypeError:
            checkpoint = torch.load(
                args.checkpoint,
                map_location="cpu",
            )

        state_dict = extract_state_dict(checkpoint)
        model.load_state_dict(state_dict, strict=True)

        device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )
        model.to(device)
        model.eval()

        true_labels = []
        predicted_labels = []
        confidences = []
        rows = []

        with torch.inference_mode():
            for images, labels in loader:
                images = images.to(device)
                logits = model(images)
                probabilities = torch.softmax(logits, dim=1)
                confidence, predictions = probabilities.max(dim=1)

                for i in range(len(labels)):
                    true_idx = int(labels[i])
                    pred_idx = int(predictions[i].cpu())
                    conf = float(confidence[i].cpu())

                    true_labels.append(true_idx)
                    predicted_labels.append(pred_idx)
                    confidences.append(conf)

                    image_path = dataset.samples[len(rows)][0]
                    rows.append({
                        "image": str(Path(image_path)),
                        "true_class": class_names[true_idx],
                        "predicted_class": class_names[pred_idx],
                        "correct": true_idx == pred_idx,
                        "top1_confidence": round(conf, 6),
                    })

        # Compute metrics over the full model label space.
        labels = list(range(len(class_names)))
        accuracy = accuracy_score(true_labels, predicted_labels)

        report = classification_report(
            true_labels,
            predicted_labels,
            labels=labels,
            target_names=class_names,
            output_dict=True,
            zero_division=0,
        )

        matrix = confusion_matrix(
            true_labels,
            predicted_labels,
            labels=labels,
        )

        # Expected calibration error (ECE), using 10 confidence bins.
        ece = 0.0
        bins = []
        for lower in [i / 10 for i in range(10)]:
            upper = lower + 0.1
            indices = [
                i for i, conf in enumerate(confidences)
                if lower <= conf < upper
                or (upper == 1.0 and conf == 1.0)
            ]

            if indices:
                bin_accuracy = sum(
                    true_labels[i] == predicted_labels[i]
                    for i in indices
                ) / len(indices)
                bin_confidence = sum(
                    confidences[i] for i in indices
                ) / len(indices)
                ece += len(indices) / len(confidences) * abs(
                    bin_accuracy - bin_confidence
                )
            else:
                bin_accuracy = None
                bin_confidence = None

            bins.append({
                "lower_confidence": round(lower, 1),
                "upper_confidence": round(upper, 1),
                "count": len(indices),
                "accuracy": bin_accuracy,
                "mean_confidence": bin_confidence,
            })

        args.output.mkdir(parents=True, exist_ok=True)

        summary = {
            "dataset": str(args.data.resolve()),
            "checkpoint": str(args.checkpoint.resolve()),
            "num_images": len(true_labels),
            "num_model_classes": len(class_names),
            "num_classes_present": len(present_classes),
            "classes_present": present_classes,
            "accuracy": float(accuracy),
            "macro_precision": float(precision_score(
                true_labels, predicted_labels,
                labels=labels, average="macro", zero_division=0,
            )),
            "macro_recall": float(recall_score(
                true_labels, predicted_labels,
                labels=labels, average="macro", zero_division=0,
            )),
            "macro_f1": float(f1_score(
                true_labels, predicted_labels,
                labels=labels, average="macro", zero_division=0,
            )),
            "mean_top1_confidence": float(sum(confidences) / len(confidences)),
            "expected_calibration_error_10_bins": float(ece),
            "note": (
                "Results apply only to these labeled images. "
                "A tiny sample is not a reliable estimate of field performance. "
                "Softmax confidence is not the probability that a prediction is correct."
            ),
        }

        (args.output / "summary.json").write_text(
            json.dumps(summary, indent=2),
            encoding="utf-8",
        )
        (args.output / "classification_report.json").write_text(
            json.dumps(report, indent=2),
            encoding="utf-8",
        )
        (args.output / "confidence_bins.json").write_text(
            json.dumps(bins, indent=2),
            encoding="utf-8",
        )

        with (args.output / "confusion_matrix.csv").open(
            "w", newline="", encoding="utf-8"
        ) as file:
            writer = csv.writer(file)
            writer.writerow(["true_class/predicted_class"] + class_names)
            for i, row in enumerate(matrix):
                writer.writerow([class_names[i]] + row.tolist())

        with (args.output / "per_image_predictions.csv").open(
            "w", newline="", encoding="utf-8"
        ) as file:
            writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

        print("\nEvaluation complete.")
        print(f"Accuracy:      {accuracy:.4f}")
        print(f"Macro precision: {summary['macro_precision']:.4f}")
        print(f"Macro recall:    {summary['macro_recall']:.4f}")
        print(f"Macro F1:        {summary['macro_f1']:.4f}")
        print(f"Mean confidence: {summary['mean_top1_confidence']:.4f}")
        print(f"10-bin ECE:      {ece:.4f}")
        print(f"Reports saved to: {args.output.resolve()}")

        return 0

    except Exception as exc:
        print(f"ERROR during evaluation: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
