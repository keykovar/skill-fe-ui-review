#!/usr/bin/env python3
"""Create an auditable sRGB copy; preserve original evidence and pixel geometry."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path

from PIL import Image, ImageCms


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_srgb(source: Path, output: Path) -> dict:
    source, output = source.resolve(), output.resolve()
    manifest = output.with_suffix(output.suffix + '.json')
    if source == output or output.exists() or manifest.exists():
        raise ValueError('Output image and manifest must be new; original evidence is never overwritten')
    destination = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB'))
    with Image.open(source) as image:
        image.load()
        profile_bytes = image.info.get('icc_profile')
        if profile_bytes:
            if image.mode not in ('RGB', 'RGBA'):
                raise ValueError('Tagged evidence must use RGB or RGBA mode')
            profile = ImageCms.ImageCmsProfile(io.BytesIO(profile_bytes))
            normalized = ImageCms.profileToProfile(image.convert('RGB'), profile, destination, outputMode='RGB', renderingIntent=0)
            profile_name = ImageCms.getProfileName(profile).strip()
        else:
            normalized = image.convert('RGB')
            profile_name = None
        if 'A' in image.getbands() or 'transparency' in image.info:
            normalized.putalpha(image.convert('RGBA').getchannel('A'))
        size = image.size
    # Decode/transform succeeds before any output is created. Keep alpha and dimensions.
    output.parent.mkdir(parents=True, exist_ok=True)
    normalized.save(output, format='PNG', icc_profile=destination.tobytes())
    record = {
        'schemaVersion': 1,
        'source': {'path': str(source), 'sha256': sha256(source), 'iccSha256': hashlib.sha256(profile_bytes).hexdigest() if profile_bytes else None, 'profileName': profile_name},
        'output': {'path': str(output), 'sha256': sha256(output), 'pixelSize': {'width': size[0], 'height': size[1]}, 'colorSpace': 'sRGB'},
        'operation': 'embedded-icc-to-srgb' if profile_bytes else 'untagged-assumed-srgb',
        'untaggedAssumption': None if profile_bytes else 'Source has no ICC profile; sRGB is an explicit assumption, not measured provenance.',
        'originalPreserved': True, 'pixelGeometryUnchanged': True,
        'renderingIntent': 'perceptual', 'engine': 'Pillow ImageCms / LittleCMS',
    }
    manifest.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        result = normalize_srgb(args.input, args.output)
    except (OSError, ValueError, ImageCms.PyCMSError) as error:
        print(json.dumps({'valid': False, 'error': str(error)}))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
