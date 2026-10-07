"""Bind manually confirmed original images to WeRead chapter/range records."""

from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path


def image_key(chapter_uid, range_value) -> tuple[int, str]:
    return int(chapter_uid), str(range_value)


def image_suffix(data: bytes) -> str:
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ".webp"
    raise ValueError("Original image must be JPEG, PNG, GIF, or WebP.")


def prepare_images(manifest: dict, base_dir: Path, book_id: str,
                   highlights: list[dict], reviews: list[dict], out_dir: Path):
    """Validate every binding before copying media; never fetch or infer images."""
    if str(manifest.get("bookId")) != str(book_id):
        raise ValueError("Image manifest bookId does not match the requested book.")
    valid_keys = {
        image_key(item["chapterUid"], item["range"])
        for item in [*highlights, *reviews]
        if item.get("chapterUid") is not None and item.get("range")
    }
    entries = manifest.get("images")
    if not isinstance(entries, list):
        raise ValueError("Image manifest must contain an images list.")
    prepared, seen = [], set()
    for entry in entries:
        key = image_key(entry["chapterUid"], entry["range"])
        if key not in valid_keys:
            raise ValueError(f"Image has no matching highlight or personal note: {key}")
        if not re.fullmatch(r"\d+-\d+", key[1]):
            raise ValueError(f"Invalid WeRead range: {key[1]}")
        source = (base_dir / entry["localPath"]).resolve()
        data = source.read_bytes()
        if len(data) > 20 * 1024 * 1024:
            raise ValueError("Image exceeds the 20 MiB document upload limit.")
        suffix = image_suffix(data)
        digest = hashlib.sha256(data).hexdigest()
        if entry.get("sha256") and entry["sha256"] != digest:
            raise ValueError(f"Image checksum mismatch: {source.name}")
        if (key, digest) in seen:
            continue
        seen.add((key, digest))
        relative = f"images/{key[0]}-{key[1]}-{digest[:12]}{suffix}"
        metadata = {
            "chapterUid": key[0], "range": key[1], "localPath": relative,
            "sha256": digest, "caption": str(entry.get("caption") or "原书插图"),
        }
        for field in ("sourceUrl", "sourceMethod"):
            if entry.get(field):
                metadata[field] = entry[field]
        prepared.append((source, metadata))

    by_key, images = {}, []
    for source, metadata in prepared:
        destination = out_dir / metadata["localPath"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source != destination.resolve():
            shutil.copyfile(source, destination)
        by_key.setdefault(image_key(metadata["chapterUid"], metadata["range"]), []).append(metadata)
        images.append(metadata)
    return by_key, images
