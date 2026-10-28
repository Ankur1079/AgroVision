
import os
import time
import zipfile
from pathlib import Path, PurePosixPath

archive = os.environ.get("PLANTVILLAGE_ARCHIVE")
destination = Path(r"C:\avdata\plantvillage")

if not archive or not Path(archive).is_file():
    raise FileNotFoundError(
        "Cached archive not found. Set PLANTVILLAGE_ARCHIVE in PowerShell."
    )

destination.mkdir(parents=True, exist_ok=True)
root = destination.resolve()

extracted = 0
skipped = 0
failed = []

with zipfile.ZipFile(archive, "r") as zf:
    members = zf.infolist()
    print(f"Verified archive entries: {len(members):,}")
    print(f"Destination: {root}")
    print("Resuming extraction; existing files will be preserved.")

    for index, member in enumerate(members, start=1):
        relative = PurePosixPath(member.filename)

        # Reject absolute paths and parent-directory traversal.
        if relative.is_absolute() or ".." in relative.parts:
            failed.append((member.filename, "Unsafe archive path"))
            continue

        target = (destination / Path(*relative.parts)).resolve()

        if target != root and root not in target.parents:
            failed.append((member.filename, "Path escapes destination"))
            continue

        if member.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue

        try:
            target.parent.mkdir(parents=True, exist_ok=True)

            # Preserve files from earlier extraction attempts.
            if target.is_file() and target.stat().st_size == member.file_size:
                skipped += 1
            else:
                # Extract to a temporary file before replacing the target.
                temp = target.with_name(target.name + ".avtmp")
                for attempt in range(3):
                    try:
                        with zf.open(member, "r") as source, open(temp, "wb") as output:
                            while True:
                                chunk = source.read(1024 * 1024)
                                if not chunk:
                                    break
                                output.write(chunk)

                        temp.replace(target)
                        extracted += 1
                        break
                    except PermissionError:
                        if attempt == 2:
                            raise
                        time.sleep(1 + attempt)
                else:
                    raise RuntimeError("Extraction retries exhausted")

        except Exception as exc:
            failed.append((member.filename, repr(exc)))
            try:
                temp = target.with_name(target.name + ".avtmp")
                if temp.exists():
                    temp.unlink()
            except Exception:
                pass

        if index % 5000 == 0:
            print(
                f"Progress: {index:,}/{len(members):,} entries | "
                f"new files: {extracted:,} | existing files: {skipped:,} | "
                f"errors: {len(failed):,}"
            )

print("\nExtraction summary")
print(f"Newly extracted files: {extracted:,}")
print(f"Existing files preserved: {skipped:,}")
print(f"Failed entries: {len(failed):,}")

if failed:
    report = destination / "extraction_failures.txt"
    report.write_text(
        "\n".join(f"{name}\t{error}" for name, error in failed),
        encoding="utf-8",
    )
    print(f"Failure report: {report}")

print(f"Dataset location: {destination}")
