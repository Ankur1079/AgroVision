
from collections import Counter
from pathlib import Path
import csv

from PIL import Image, UnidentifiedImageError

DATASET_DIR = Path(r"C:\avdata\plantvillage\raw\color")
REPORT_DIR = Path(__file__).resolve().parent / "evaluation"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

if not DATASET_DIR.is_dir():
    raise FileNotFoundError(f"Dataset directory not found: {DATASET_DIR}")

class_dirs = sorted(p for p in DATASET_DIR.iterdir() if p.is_dir())

if not class_dirs:
    raise RuntimeError(f"No class directories found in {DATASET_DIR}")

rows = []
total_files = 0
total_valid = 0
total_invalid = 0

for class_dir in class_dirs:
    valid = 0
    invalid = 0

    image_files = (
        p for p in class_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    )

    for image_path in image_files:
        total_files += 1
        try:
            with Image.open(image_path) as image:
                image.verify()
            valid += 1
        except (OSError, ValueError, UnidentifiedImageError):
            invalid += 1
            print(f"INVALID: {image_path}")

    total_valid += valid
    total_invalid += invalid

    rows.append({
        "class_name": class_dir.name,
        "image_count": valid + invalid,
        "valid_images": valid,
        "invalid_images": invalid,
    })

    print(f"{class_dir.name}: valid={valid}, invalid={invalid}")

report_path = REPORT_DIR / "plantvillage_class_counts.csv"

with report_path.open("w", newline="", encoding="utf-8") as csv_file:
    writer = csv.DictWriter(
        csv_file,
        fieldnames=[
            "class_name",
            "image_count",
            "valid_images",
            "invalid_images",
        ],
    )
    writer.writeheader()
    writer.writerows(rows)

print("\n--- Verification Summary ---")
print(f"Classes found: {len(class_dirs)}")
print(f"Total image files: {total_files}")
print(f"Valid images: {total_valid}")
print(f"Invalid images: {total_invalid}")
print(f"CSV report: {report_path}")

if len(class_dirs) != 38:
    print("WARNING: Expected 38 PlantVillage color classes.")
if total_invalid:
    print("WARNING: Invalid images found; inspect them before training.")
elif len(class_dirs) == 38:
    print("Image verification passed. Review class counts before training.")
