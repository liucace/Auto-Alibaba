from pathlib import Path

from PIL import Image

from app.products.main_images import media_fingerprint, prepare_square_image


def test_prepare_square_image_adds_white_padding_without_overwriting_source(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.png"
    output = tmp_path / "optimized" / "square.jpg"
    Image.new("RGB", (1200, 800), (10, 20, 30)).save(source)
    original = source.read_bytes()

    result = prepare_square_image(source, output)

    assert result == output
    assert source.read_bytes() == original
    assert output.stat().st_size < 5_000_000
    with Image.open(output) as prepared:
        assert prepared.mode == "RGB"
        assert prepared.width == prepared.height
        assert prepared.width <= 2000
        assert prepared.getpixel((prepared.width // 2, 0))[0] >= 245


def test_media_fingerprint_changes_with_file_content(tmp_path: Path) -> None:
    first = tmp_path / "first.jpg"
    second = tmp_path / "second.jpg"
    first.write_bytes(b"first-v1")
    second.write_bytes(b"second")
    before = media_fingerprint((first, second))

    first.write_bytes(b"first-v2")

    assert media_fingerprint((first, second)) != before
