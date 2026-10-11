#!/usr/bin/env python3
"""Prepare, never publish, the original-art character feed version 2.

Retains all 100 bundled character records and adds genuine semantic animal
and fantasy illustrations. Remote URLs remain absent for the publisher to
populate from verified content-addressed object paths. No network or auth.
"""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
import import_fendoku_characters as seed
from PIL import Image

OUTPUT = seed.ROOT / "Mouse Out/Release/character-feed-v2-preparation"
COLLECTIONS = {"animal-breeds", "animal-species", "fantasy-creatures", "alien-creatures"}


def character_name(item: dict, variant: dict) -> str:
    label = variant["label"]
    if variant["collection_id"] == "animal-breeds":
        species = "cat" if item["token"] == "🐱" else "dog"
        if label.endswith(" — Head"):
            return label.removesuffix(" — Head") + f" {species} portrait"
        return label.removesuffix(" — Full Body") + f" {species}"
    return label


def prepare(source: Path) -> dict[str, bytes]:
    original_files, seed_receipt = seed.prepare(source)
    original = json.loads(original_files["MouseCharacterManifest.json"])
    if (seed.DESTINATION / "MouseCharacterManifest.json").read_bytes() != original_files["MouseCharacterManifest.json"]:
        raise ValueError("Bundled manifest differs from the approved source seed")
    characters = original["characters"].copy()
    ids = {row["id"] for row in characters}
    image_ids = {row["image"]["sha256"]: row["id"] for row in characters}
    duplicate_sources = []
    files = {name: data for name, data in original_files.items() if name.endswith(".png")}
    manifest = json.loads((source / seed.SOURCE_MANIFEST).read_bytes())
    for item in manifest["items"]:
        for variant in item["variants"]:
            identifier = variant["asset_name"]
            if variant["collection_id"] not in COLLECTIONS or identifier in ids:
                continue
            relative = f"Fendoku/Assets.xcassets/OriginalArtwork/{identifier}.imageset/art.png"
            data = (source / relative).read_bytes()
            if data != seed.git_blob(source, relative):
                raise ValueError(f"Uncommitted artwork: {identifier}")
            if seed.sha(data) in image_ids:
                duplicate_sources.append({"id": identifier, "label": variant["label"],
                                          "duplicateOf": image_ids[seed.sha(data)], "sha256": seed.sha(data)})
                continue
            if not data.startswith(b"\x89PNG\r\n\x1a\n") or not 0 < len(data) <= 2_097_152:
                raise ValueError(f"Invalid PNG: {identifier}")
            with Image.open(io.BytesIO(data)) as image:
                image.load()
                width, height = image.size
                if image.format != "PNG" or image.mode != "RGBA" or not (1 <= width <= 2048 and 1 <= height <= 2048):
                    raise ValueError(f"Invalid image dimensions or mode: {identifier}")
                alpha = image.getchannel("A")
                if alpha.getbbox() is None or alpha.getextrema()[0] == 255:
                    raise ValueError(f"Invalid transparent silhouette: {identifier}")
            if variant["collection_id"] == "animal-breeds":
                collection = "Pets & woodland"
            elif variant["collection_id"] in {"fantasy-creatures", "alien-creatures"}:
                collection = "Fantasy"
            else:
                collection = "Ocean & water" if item["token"] == "🐟" else "Wild & farm"
            filename = identifier + ".png"
            files[filename] = data
            characters.append({
                "id": identifier, "name": character_name(item, variant), "collection": collection,
                "tags": list(dict.fromkeys(["character", *variant["tags"]])), "bundledResource": filename,
                "image": {"sha256": seed.sha(data), "byteCount": len(data), "pixelWidth": width, "pixelHeight": height},
                "source": {"repository": "fennelouski/Fendoku", "commit": seed.SOURCE_COMMIT,
                           "assetName": identifier, "assetPath": relative, "token": item["token"],
                           "variantID": variant["id"], "variantLabel": variant["label"],
                           "semanticDescription": item["description"], "collectionID": variant["collection_id"],
                           "sha256": seed.sha(data)}
            })
            ids.add(identifier)
            image_ids[seed.sha(data)] = identifier
    if len(characters) != 209 or len(image_ids) != 209 or characters[:100] != original["characters"]:
        raise ValueError("Expected 209 distinct source images with the original 100 records intact")
    catalog = {"schemaVersion": 1, "version": 2, "characters": characters}
    files["MouseCharacterManifest.json"] = seed.encoded(catalog)
    if len(files["MouseCharacterManifest.json"]) > 2_097_152:
        raise ValueError("Feed exceeds manifest byte limit")
    receipt = {
        "schemaVersion": 1, "status": "local_unpublished_preparation", "version": 2,
        "characterCount": 209, "originalSeedCount": 100, "additionalCharacterCount": 109,
        "seedManifestSHA256": seed_receipt["catalogSHA256"],
        "allOriginal100FieldsPreserved": True,
        "sourceRepository": seed_receipt["sourceRepository"], "sourceCommit": seed.SOURCE_COMMIT,
        "sourceManifestSHA256": seed.SOURCE_MANIFEST_SHA256,
        "reuseBasis": seed_receipt["reuseBasis"],
        "includedAdditionalSourceCollections": sorted(COLLECTIONS),
        "excludedExactDuplicateSources": duplicate_sources,
        "selectionRationale": "Animal breeds, species and recognizable fantasy creatures extend character choice. Instruments, tools, tableware and footprint markers are excluded rather than inflating the count with objects.",
        "collections": {name: sum(row["collection"] == name for row in characters)
                        for name in dict.fromkeys(row["collection"] for row in characters)},
        "imageBytes": sum(row["image"]["byteCount"] for row in characters),
        "maximumImageBytes": max(row["image"]["byteCount"] for row in characters),
        "sourceImageTransformations": "None; exact committed Fendoku PNG bytes",
        "catalogSHA256": seed.sha(files["MouseCharacterManifest.json"]),
        "filesSHA256": {name: seed.sha(data) for name, data in files.items()},
        "remoteURLs": "Omitted. The backend owner will construct and verify the allowlisted HTTPS object URL for each hash. These extra109 files are not in the native100 seed.",
        "published": False, "credentialsAccessed": False, "fendokuModified": False,
        "scriptsSHA256": {"Scripts/import_fendoku_characters.py": seed.sha(Path(seed.__file__).read_bytes()),
                          "Scripts/prepare_character_feed.py": seed.sha(Path(__file__).read_bytes())},
        "verifyCommand": "python3 Scripts/prepare_character_feed.py --check --fendoku-root /Users/nathan/Documents/GitHub/Fendoku"
    }
    files["provenance.json"] = seed.encoded(receipt)
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fendoku-root", type=Path, default=seed.ROOT.parent / "Fendoku")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files = prepare(args.fendoku_root.resolve())
    if args.write:
        for name, data in files.items():
            existing = OUTPUT / name
            if existing.exists() and existing.read_bytes() != data:
                raise ValueError(f"Conflicting existing preparation file: {name}")
        OUTPUT.mkdir(parents=True, exist_ok=True)
        for name, data in files.items():
            (OUTPUT / name).write_bytes(data)
    for name, data in files.items():
        if (OUTPUT / name).read_bytes() != data:
            raise ValueError(f"Prepared bytes mismatch: {name}")
    print(json.dumps({"verifiedCharacters": 209, "catalogSHA256": seed.sha(files["MouseCharacterManifest.json"]),
                      "provenanceSHA256": seed.sha(files["provenance.json"])}, indent=2))


if __name__ == "__main__":
    main()
