#!/usr/bin/env python3
"""Copy the approved 100-character Fendoku seed without changing source pixels.

Use --write to import, or --check to verify the existing bundle. No network,
credentials, native build, image transformation or Fendoku mutation occurs.
Requires Pillow only for decoding and validating source PNGs.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE_COMMIT = "1d42ab801b2aedc4403cd28edf3c3e1ba1ba7937"
SOURCE_MANIFEST = "docs/original-art-assets.json"
SOURCE_MANIFEST_SHA256 = "cf1c513e84775c41343330a48c575a2c6ca3f93ba360db1e1eb4c973e8e0eb36"
DESTINATION = ROOT / "Mouse Out/Mouse Out/Characters"
PROVENANCE = ROOT / "Mouse Out/Release/character-import-provenance.json"

# Deliberate semantic choices, never automatic substring selection. Keep IDs
# stable when labels or collection presentation change. No material duplicates.
SELECTION = """
art-emoji-1f42d|Mouse|Pets & woodland
art-emoji-1f400|Rat|Pets & woodland
art-emoji-1f439|Hamster|Pets & woodland
art-emoji-1f430|Rabbit portrait|Pets & woodland
art-emoji-1f407|Rabbit|Pets & woodland
art-emoji-1f431|Cat|Pets & woodland
art-emoji-1f640|Weary cat|Pets & woodland
art-emoji-1f431-cat-siamese|Siamese cat|Pets & woodland
art-emoji-1f436|Dog|Pets & woodland
art-emoji-1f436-dog-corgi|Corgi|Pets & woodland
art-emoji-1f98a|Fox|Pets & woodland
art-emoji-1f43a|Wolf|Pets & woodland
art-emoji-1f43b|Bear|Pets & woodland
art-emoji-1f43c|Panda|Pets & woodland
art-emoji-1f428|Koala|Pets & woodland
art-emoji-1f9a5|Sloth|Pets & woodland
art-emoji-1f994|Hedgehog|Pets & woodland
art-emoji-1f99d|Raccoon|Pets & woodland
art-emoji-1f9a6|Otter|Pets & woodland
art-emoji-1f9ab|Beaver|Pets & woodland
art-emoji-1f9a8|Skunk|Pets & woodland
art-emoji-1f9a1|Badger|Pets & woodland
art-emoji-1f43f-fe0f|Chipmunk|Pets & woodland
art-emoji-1f987|Bat|Pets & woodland
art-emoji-1f412|Monkey|Wild & farm
art-emoji-1f40e|Horse|Wild & farm
art-emoji-1f434|Horse portrait|Wild & farm
art-emoji-1f998|Kangaroo|Wild & farm
art-emoji-1face|Moose|Wild & farm
art-emoji-1f992|Giraffe|Wild & farm
art-emoji-1f406|Leopard|Wild & farm
art-emoji-1f993|Zebra|Wild & farm
art-emoji-1f42b|Camel|Wild & farm
art-emoji-1f98c|Deer|Wild & farm
art-emoji-1f404|Cow|Wild & farm
art-emoji-1f437|Pig|Wild & farm
art-emoji-1f411|Sheep|Wild & farm
art-emoji-1f410|Goat|Wild & farm
art-emoji-1f999|Llama|Wild & farm
art-emoji-1f9ac|Bison|Wild & farm
art-emoji-1f98d|Gorilla|Wild & farm
art-emoji-1f98f|Rhinoceros|Wild & farm
art-emoji-1f418|Elephant|Wild & farm
art-emoji-1f99b|Hippopotamus|Wild & farm
art-emoji-1f42f|Tiger|Wild & farm
art-emoji-1f981|Lion|Wild & farm
art-emoji-1f40a|Crocodile|Wild & farm
art-emoji-1f40d|Snake|Wild & farm
art-emoji-1f422|Turtle|Wild & farm
art-emoji-1f98e|Lizard|Wild & farm
art-emoji-1f438|Frog|Wild & farm
art-emoji-1f98e-lizard-gecko|Gecko|Wild & farm
art-emoji-1f99c|Parrot|Birds
art-emoji-1f989|Owl|Birds
art-emoji-1f985|Eagle|Birds
art-emoji-1f9a2|Swan|Birds
art-emoji-1f427|Penguin|Birds
art-emoji-1f9a9|Flamingo|Birds
art-emoji-1f986|Duck|Birds
art-emoji-1f413|Rooster|Birds
art-emoji-1f423|Hatching chick|Birds
art-emoji-1f424|Chick|Birds
art-emoji-1f54a-fe0f|Dove|Birds
art-emoji-1f983|Turkey|Birds
art-emoji-1f9a4|Dodo|Birds
art-emoji-1f425|Front-facing chick|Birds
art-emoji-1f414|Chicken|Birds
art-emoji-1f41f|Fish|Ocean & water
art-emoji-1f419|Octopus|Ocean & water
art-emoji-1f420|Tropical fish|Ocean & water
art-emoji-1f433|Spouting whale|Ocean & water
art-emoji-1f40b|Whale|Ocean & water
art-emoji-1f99e|Lobster|Ocean & water
art-emoji-1f980|Crab|Ocean & water
art-emoji-1f42c|Dolphin|Ocean & water
art-emoji-1f9ad|Seal|Ocean & water
art-emoji-1f988|Shark|Ocean & water
art-emoji-1f990|Shrimp|Ocean & water
art-emoji-1f991|Squid|Ocean & water
art-emoji-1fabc|Jellyfish|Ocean & water
art-emoji-1f9aa|Oyster|Ocean & water
art-emoji-1f41f-fish-goldfish|Goldfish|Ocean & water
art-emoji-1f41d|Honeybee|Tiny creatures
art-emoji-1f98b|Butterfly|Tiny creatures
art-emoji-1fab2|Beetle|Tiny creatures
art-emoji-1f40c|Snail|Tiny creatures
art-emoji-1f982|Scorpion|Tiny creatures
art-emoji-1f577-fe0f|Spider|Tiny creatures
art-emoji-1f41c|Ant|Tiny creatures
art-emoji-1f99f|Mosquito|Tiny creatures
art-emoji-1f41e|Ladybird|Tiny creatures
art-emoji-1f997|Cricket|Tiny creatures
art-emoji-1fab0|Fly|Tiny creatures
art-emoji-1fab1|Worm|Tiny creatures
art-emoji-1f916|Robot|Fantasy
art-emoji-1f47e|Alien monster|Fantasy
art-emoji-1f984|Unicorn|Fantasy
art-emoji-1f995|Dinosaur|Fantasy
art-emoji-1f409|Dragon|Fantasy
art-emoji-1f47d|Alien|Fantasy
"""


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def git_blob(source: Path, relative: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{SOURCE_COMMIT}:{relative}"], cwd=source)


def prepare(source: Path) -> tuple[dict[str, bytes], dict]:
    manifest_bytes = (source / SOURCE_MANIFEST).read_bytes()
    if sha(manifest_bytes) != SOURCE_MANIFEST_SHA256 or git_blob(source, SOURCE_MANIFEST) != manifest_bytes:
        raise ValueError("Fendoku manifest differs from the approved pinned input")
    manifest = json.loads(manifest_bytes)
    variants = {variant["asset_name"]: (item, variant)
                for item in manifest["items"] for variant in item["variants"]}
    selections = [line.split("|") for line in SELECTION.strip().splitlines()]
    if len(selections) != 100 or len({row[0] for row in selections}) != 100:
        raise ValueError("The starter selection must contain 100 distinct stable IDs")
    images: dict[str, bytes] = {}
    characters = []
    for identifier, name, collection in selections:
        item, variant = variants[identifier]
        source_path = f"Fendoku/Assets.xcassets/OriginalArtwork/{identifier}.imageset/art.png"
        data = (source / source_path).read_bytes()
        if data != git_blob(source, source_path):
            raise ValueError(f"Uncommitted source artwork: {identifier}")
        if not data.startswith(b"\x89PNG\r\n\x1a\n") or not 0 < len(data) <= 2_097_152:
            raise ValueError(f"Invalid or oversized PNG: {identifier}")
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            width, height = image.size
            if image.format != "PNG" or image.mode != "RGBA" or not (1 <= width <= 2048 and 1 <= height <= 2048):
                raise ValueError(f"Invalid PNG dimensions or pixel mode: {identifier}")
            alpha = image.getchannel("A")
            if alpha.getbbox() is None or alpha.getextrema()[0] == 255:
                raise ValueError(f"Artwork lacks a visible transparent silhouette: {identifier}")
        filename = identifier + ".png"
        images[filename] = data
        characters.append({
            "id": identifier, "name": name, "collection": collection,
            "tags": list(dict.fromkeys(["character", collection.lower().replace(" & ", "-").replace(" ", "-"),
                                        *name.lower().split(), *variant["tags"]])),
            "bundledResource": filename,
            "image": {"sha256": sha(data), "byteCount": len(data), "pixelWidth": width, "pixelHeight": height},
            "source": {"repository": "fennelouski/Fendoku", "commit": SOURCE_COMMIT,
                       "assetName": identifier, "assetPath": source_path, "token": item["token"],
                       "variantID": variant["id"], "variantLabel": variant["label"],
                       "semanticDescription": item["description"], "collectionID": variant["collection_id"],
                       "sha256": sha(data)}
        })
    catalog = {"schemaVersion": 1, "version": 1, "characters": characters}
    images["MouseCharacterManifest.json"] = encoded(catalog)
    if len(images["MouseCharacterManifest.json"]) > 2_097_152:
        raise ValueError("Character catalog exceeds client manifest limit")
    original_seed = ROOT / "Mouse Out/Release/asset-provenance.json"
    earlier = json.loads(original_seed.read_bytes())
    existing_ids = {row["asset_name"] for row in earlier["artwork"]}
    existing_reused = sorted(existing_ids.intersection(row["id"] for row in characters))
    receipt = {
        "schemaVersion": 1, "selectionRevision": "mouse-out-characters-v1", "selectionDate": "2026-10-04",
        "sourceRepository": "fennelouski/Fendoku", "sourceCommit": SOURCE_COMMIT,
        "sourceManifest": SOURCE_MANIFEST, "sourceManifestSHA256": SOURCE_MANIFEST_SHA256,
        "reuseBasis": "User-approved Fendoku original artwork reuse, recorded in shared app-design-guidelines.md and the existing Mouse Out/Release/asset-provenance.json. No new license or original-generation rights audit is asserted.",
        "priorMouseAssetReceiptSHA256": sha(original_seed.read_bytes()),
        "characterCount": len(characters), "coreGouacheCount": sum(row["source"]["variantID"] == "gouache" for row in characters),
        "semanticVariantCount": sum(row["source"]["variantID"] != "gouache" for row in characters),
        "collections": {name: sum(row["collection"] == name for row in characters)
                        for name in dict.fromkeys(row["collection"] for row in characters)},
        "imageByteCount": sum(row["image"]["byteCount"] for row in characters),
        "imageTransformation": "None. Every bundled PNG is byte-identical to its pinned committed Fendoku source.",
        "dimensions": "100 RGBA PNGs, each 314x314 pixels, with visible art and transparent pixels.",
        "catalogPath": "Mouse Out/Mouse Out/Characters/MouseCharacterManifest.json",
        "catalogSHA256": sha(images["MouseCharacterManifest.json"]),
        "bundledFilesSHA256": {name: sha(data) for name, data in images.items()},
        "existing17CompiledImagesets": "Preserved unchanged. The raw bundle keeps the same source artwork available to the verified offline/remote byte loader; old compiled assets remain for compatibility.",
        "existingArtworkIDsAlsoInCatalog": existing_reused,
        "legacyPlayableCharacterMap": {
            "mouse": "art-emoji-1f42d", "cat": "art-emoji-1f431", "dog": "art-emoji-1f436",
            "fox": "art-emoji-1f98a", "bear": "art-emoji-1f43b", "panda": "art-emoji-1f43c",
            "koala": "art-emoji-1f428", "lion": "art-emoji-1f981", "tiger": "art-emoji-1f42f",
            "pig": "art-emoji-1f437", "frog": "art-emoji-1f438", "monkey": "art-emoji-1f412",
            "penguin": "art-emoji-1f427", "unicorn": "art-emoji-1f984", "owl": "art-emoji-1f989",
            "rabbit": "art-emoji-1f430", "raccoon": "art-emoji-1f99d", "hamster": "art-emoji-1f439",
            "chicken": "art-emoji-1f414", "duck": "art-emoji-1f986", "turtle": "art-emoji-1f422",
            "octopus": "art-emoji-1f419", "wolf": "art-emoji-1f43a", "bee": "art-emoji-1f41d",
            "dragon": "art-emoji-1f409"
        },
        "legacyTokenException": "Legacy monkey uses the glyph U+1F435, absent from Fendoku. Map its case to the genuine Fendoku Monkey U+1F412 source artwork; do not invent or duplicate a U+1F435 asset identity.",
        "remoteURLs": "Omitted. This import does not publish or configure an endpoint; the backend owner must verify any future allowlisted URLs.",
        "fendokuChanged": False, "nativeFilesChanged": False, "backendChanged": False,
        "importScript": "Scripts/import_fendoku_characters.py",
        "importScriptSHA256": sha(Path(__file__).read_bytes()),
        "verifyCommand": "python3 Scripts/import_fendoku_characters.py --check --fendoku-root /Users/nathan/Documents/GitHub/Fendoku"
    }
    return images, receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fendoku-root", type=Path, default=ROOT.parent / "Fendoku")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files, receipt = prepare(args.fendoku_root.resolve())
    if args.write:
        # Refuse conflicting output instead of silently overwriting later assets.
        for name, data in files.items():
            existing = DESTINATION / name
            if existing.exists() and existing.read_bytes() != data:
                raise ValueError(f"Conflicting existing bundle file: {existing}")
        if PROVENANCE.exists() and PROVENANCE.read_bytes() != encoded(receipt):
            raise ValueError("Conflicting existing provenance receipt")
        DESTINATION.mkdir(parents=True, exist_ok=True)
        for name, data in files.items():
            (DESTINATION / name).write_bytes(data)
        PROVENANCE.parent.mkdir(parents=True, exist_ok=True)
        PROVENANCE.write_bytes(encoded(receipt))
    for name, data in files.items():
        if (DESTINATION / name).read_bytes() != data:
            raise ValueError(f"Bundled bytes mismatch: {name}")
    if PROVENANCE.read_bytes() != encoded(receipt):
        raise ValueError("Provenance receipt differs from the deterministic import")
    print(json.dumps({"verifiedCharacters": 100, "catalogSHA256": receipt["catalogSHA256"],
                      "provenanceSHA256": sha(PROVENANCE.read_bytes()), "imageBytes": receipt["imageByteCount"],
                      "collections": receipt["collections"]}, indent=2))


if __name__ == "__main__":
    main()
