"""Regression tests for the texture gate.

Three false-passes were found by the sprite_strategist subagent and confirmed by
hand before this file existed; each one is a case below. Pillow only, no network.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "pipeline" / "verify_wa.py"


def gate(*paths) -> tuple[int, str]:
    r = subprocess.run([sys.executable, str(VERIFY), *[str(p) for p in paths]],
                       capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def figure_texture(tmp: Path, name: str = "t.png") -> Path:
    """A minimal but legitimate texture: a figure in all twelve cells."""
    tex = Image.new("RGBA", (96, 128), (0, 0, 0, 0))
    for r in range(4):
        for c in range(3):
            for y in range(r * 32 + 1, r * 32 + 31):   # exactly 30px tall
                for x in range(c * 32 + 12, c * 32 + 21):
                    tex.putpixel((x, y), (70, 110, 160, 255))
    p = tmp / name
    tex.save(p)
    return p


class GateTests(unittest.TestCase):
    def test_valid_texture_passes(self):
        with tempfile.TemporaryDirectory() as d:
            rc, out = gate(figure_texture(Path(d)))
        self.assertEqual(rc, 0, out)
        self.assertIn("ALL PASS", out)

    def test_wrong_size_fails_instead_of_being_skipped(self):
        """A texture named like a texture but sized 48x64 must fail, not skip."""
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "wrong_texture_96x128.png"
            Image.new("RGBA", (48, 64), (10, 200, 40, 255)).save(p)
            rc, out = gate(p)
        self.assertNotEqual(rc, 0, "a wrong-sized texture must fail the gate")
        self.assertIn("must be (96, 128)", out)

    def test_fully_opaque_texture_fails(self):
        """No transparent pixels means the matte failed open: not a woka."""
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "opaque_texture_96x128.png"
            Image.new("RGB", (96, 128), (180, 40, 40)).save(p)
            rc, out = gate(p)
        self.assertNotEqual(rc, 0, "a texture with no empty space must fail")
        self.assertIn("no transparent pixels", out)

    def test_empty_walk_cells_fail(self):
        """Every cell must hold a frame, not just the standing column."""
        with tempfile.TemporaryDirectory() as d:
            tex = Image.open(figure_texture(Path(d))).convert("RGBA")
            for r in range(4):
                for c in (0, 2):
                    tex.paste(Image.new("RGBA", (32, 32), (0, 0, 0, 0)), (c * 32, r * 32))
            p = Path(d) / "empty_steps_texture_96x128.png"
            tex.save(p)
            rc, out = gate(p)
        self.assertNotEqual(rc, 0, "empty walk frames must fail")
        self.assertIn("is empty", out)

    def test_short_character_still_fails(self):
        with tempfile.TemporaryDirectory() as d:
            tex = Image.new("RGBA", (96, 128), (0, 0, 0, 0))
            for r in range(4):
                for c in range(3):
                    for y in range(r * 32 + 14, r * 32 + 30):
                        for x in range(c * 32 + 14, c * 32 + 19):
                            tex.putpixel((x, y), (70, 110, 160, 255))
            p = Path(d) / "short_texture_96x128.png"
            tex.save(p)
            rc, out = gate(p)
        self.assertNotEqual(rc, 0, "a 16px-tall figure must fail")
        self.assertIn("it will look tiny in game", out)

    def test_previews_are_skipped_not_failed(self):
        """Preview images beside a texture are verified through the texture."""
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            tex = Image.open(figure_texture(d)).convert("RGBA")
            Image.new("RGBA", (768, 1024), (0, 0, 0, 0)).save(d / "t_sheet_8x.png")
            tex.crop((32, 0, 64, 32)).save(d / "idle_down.png")   # a real idle still
            rc, out = gate(d / "t.png", d / "t_sheet_8x.png", d / "idle_down.png")
        self.assertEqual(rc, 0, out)
        self.assertIn("SKIP", out)

    def test_every_committed_texture_passes(self):
        textures = sorted((ROOT / "characters").glob("*/*_texture_96x128.png"))
        self.assertGreaterEqual(len(textures), 4, "expected the committed characters")
        rc, out = gate(*textures)
        self.assertEqual(rc, 0, out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
