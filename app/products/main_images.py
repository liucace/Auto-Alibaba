import hashlib
from pathlib import Path

from PIL import Image

MAX_EDGE = 2000
MAX_IMAGE_BYTES = 5_000_000


def prepare_square_image(source: Path, output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as opened:
        image = opened.convert("RGB")
        image.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)
        side = max(image.size)
        canvas = Image.new("RGB", (side, side), "white")
        offset = ((side - image.width) // 2, (side - image.height) // 2)
        canvas.paste(image, offset)
        temporary = output.with_suffix(output.suffix + ".tmp")
        canvas.save(temporary, format="JPEG", quality=90, optimize=True)
        if temporary.stat().st_size >= MAX_IMAGE_BYTES:
            temporary.unlink(missing_ok=True)
            raise ValueError(f"prepared main image exceeds 5,000,000 bytes: {source}")
        temporary.replace(output)
    return output


def media_fingerprint(paths: tuple[Path, ...]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        content = path.read_bytes()
        digest.update(path.name.encode("utf-8"))
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(hashlib.sha256(content).digest())
    return digest.hexdigest()
