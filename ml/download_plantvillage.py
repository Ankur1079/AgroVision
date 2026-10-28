
from pathlib import Path

import datasets
from datasets import load_dataset, load_from_disk
from huggingface_hub import hf_hub_download
from packaging.version import Version

ML_DIR = Path(__file__).resolve().parent
DATA_DIR = ML_DIR / "data"
CACHE_DIR = DATA_DIR / "hf_cache"
DATASET_DIR = DATA_DIR / "plantvillage"

if Version(datasets.__version__) >= Version("4.0.0"):
    raise RuntimeError(
        "PlantVillage requires the legacy Hugging Face dataset loader. "
        "Install the compatible dependency with "
        "`python -m pip install -r ml/requirements.txt` from the repository root."
    )

DATA_DIR.mkdir(parents=True, exist_ok=True)

# Avoid overwriting an existing dataset.
if DATASET_DIR.exists():
    print(f"Dataset directory already exists: {DATASET_DIR}")
    print("Checking whether it contains a saved dataset...")

    try:
        existing = load_from_disk(str(DATASET_DIR))
        print(existing)
        print("Existing dataset is readable. No download performed.")
        raise SystemExit(0)
    except (FileNotFoundError, ValueError, OSError):
        print("No readable saved dataset found. Continuing download.")

print("Loading the real PlantVillage color dataset...")

dataset_script = hf_hub_download(
    repo_id="mohanty/PlantVillage",
    filename="plant_village.py",
    repo_type="dataset",
    cache_dir=str(CACHE_DIR),
)

dataset = load_dataset(
    dataset_script,
    name="default",
    cache_dir=str(CACHE_DIR),
    trust_remote_code=True,
)

print("\nDataset split information:")
for split_name, split_data in dataset.items():
    print(f"{split_name}: {len(split_data):,} images")

first_split = dataset[next(iter(dataset.keys()))]
print("\nColumns:", first_split.column_names)
print("Features:", first_split.features)

print("\nSaving dataset locally...")
dataset.save_to_disk(str(DATASET_DIR))

print(f"\nDataset saved at: {DATASET_DIR}")
print("Download and local save completed.")
