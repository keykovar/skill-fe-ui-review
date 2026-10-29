from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('normalize_srgb', ROOT / 'skills/fe-ui-review/scripts/normalize_srgb.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class NormalizeSrgbTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_capture_profile_maps_control_color_to_css_srgb_and_preserves_alpha(self):
        control = json.loads((ROOT / 'tests/fixtures/capture-color-profile.json').read_text())
        profile = base64.b64decode(control['base64'])
        self.assertEqual(hashlib.sha256(profile).hexdigest(), control['sha256'])
        source, output = self.root/'original.png', self.root/'normalized.png'
        Image.new('RGBA', (7, 3), (*control['encodedRgb'], 81)).save(source, icc_profile=profile)
        before = source.read_bytes()
        result = MODULE.normalize_srgb(source, output)
        with Image.open(output) as image:
            self.assertEqual(image.size, (7, 3))
            self.assertEqual(image.getpixel((0, 0)), (*control['expectedSrgb'], 81))
            self.assertIn('icc_profile', image.info)
        self.assertEqual(source.read_bytes(), before)
        self.assertEqual(result['operation'], 'embedded-icc-to-srgb')
        self.assertEqual(result['source']['sha256'], hashlib.sha256(before).hexdigest())
        self.assertEqual(json.loads(output.with_suffix('.png.json').read_text()), result)

    def test_untagged_assumption_is_recorded_and_pixels_stay_equal(self):
        source, output = self.root/'original.png', self.root/'normalized.png'
        Image.new('RGB', (2, 2), (172, 52, 88)).save(source)
        result = MODULE.normalize_srgb(source, output)
        self.assertEqual(result['operation'], 'untagged-assumed-srgb')
        self.assertTrue(result['untaggedAssumption'])
        with Image.open(output) as image:
            self.assertEqual(image.getpixel((1, 1)), (172, 52, 88))

    def test_existing_output_is_preserved(self):
        source, output = self.root/'original.png', self.root/'normalized.png'
        Image.new('RGB', (2, 2)).save(source)
        output.write_bytes(b'existing evidence')
        with self.assertRaises(ValueError):
            MODULE.normalize_srgb(source, output)
        self.assertEqual(output.read_bytes(), b'existing evidence')

    def test_invalid_profile_does_not_create_output(self):
        source, output = self.root/'original.png', self.root/'normalized.png'
        Image.new('RGB', (2, 2)).save(source, icc_profile=b'invalid profile')
        with self.assertRaises(OSError):
            MODULE.normalize_srgb(source, output)
        self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
