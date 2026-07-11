from html.parser import HTMLParser
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
DETAIL = ROOT / "automation" / "A2E250-AL06-01" / "detail.html"
CONFIG = ROOT / "config" / "detail_templates.yaml"
MODEL = "A2E250-AL06-01"
FOURTH_IMAGE = (
    "https://cbu01.alicdn.com/img/ibank/"
    "O1CN01q5O6eR1fBr8ZyQuxj_!!994523969-0-cib.jpg"
)
WHITE_BACKGROUND_IMAGE = (
    "https://cbu01.alicdn.com/img/ibank/"
    "O1CN01DOdda51fBr8aDYZNw_!!994523969-0-cib.jpg"
)


class ImageCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.images: list[dict[str, str]] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag.lower() == "img":
            self.images.append({key: value or "" for key, value in attrs})


class GeoDetailArtifactTest(unittest.TestCase):
    def test_detail_uses_four_distinct_semantic_current_model_images(self) -> None:
        parser = ImageCollector()
        parser.feed(DETAIL.read_text(encoding="utf-8"))

        sources = [image["src"] for image in parser.images]
        self.assertEqual(4, len(sources))
        self.assertEqual(4, len(set(sources)))
        self.assertIn(FOURTH_IMAGE, sources)
        self.assertNotIn(WHITE_BACKGROUND_IMAGE, sources)
        self.assertTrue(all(MODEL in image.get("alt", "") for image in parser.images))

    def test_detail_config_requires_four_images(self) -> None:
        config = CONFIG.read_text(encoding="utf-8")
        match = re.search(r"required_count:\s*(\d+)", config)

        self.assertIsNotNone(match)
        self.assertEqual("4", match.group(1))
        self.assertIn("fourth_image_role: nameplate_closeup", config)
        self.assertIn("reject_white_background: true", config)
        self.assertIn("reject_duplicate_urls: true", config)
        self.assertIn("form_model_sync: updateModelValue", config)
        self.assertIn("quality_payload_must_not_be_null: true", config)


if __name__ == "__main__":
    unittest.main()
