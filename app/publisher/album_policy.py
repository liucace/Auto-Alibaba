import re
from dataclasses import dataclass


@dataclass(frozen=True)
class BrandAlbum:
    name: str
    number: int


@dataclass(frozen=True)
class AlbumChoice:
    name: str
    create: bool


def _clean_brand(brand: str) -> str:
    clean = brand.strip()
    if not clean:
        raise ValueError("brand is required")
    return clean


def brand_album_name(brand: str, number: int) -> str:
    clean = _clean_brand(brand)
    if number < 1:
        raise ValueError("positive album number is required")
    return f"{clean}({number:02d})"


def matching_brand_albums(brand: str, names: list[str]) -> tuple[BrandAlbum, ...]:
    clean = _clean_brand(brand)
    pattern = re.compile(rf"{re.escape(clean)}\((\d{{2,}})\)", flags=re.IGNORECASE)
    matches = [
        BrandAlbum(name=name.strip(), number=int(match.group(1)))
        for name in names
        if (match := pattern.fullmatch(name.strip())) is not None
    ]
    return tuple(sorted(matches, key=lambda item: item.number))


def choose_brand_album(brand: str, names: list[str]) -> AlbumChoice:
    matches = matching_brand_albums(brand, names)
    return AlbumChoice(
        name=matches[-1].name if matches else brand_album_name(brand, 1),
        create=not matches,
    )


def next_brand_album(brand: str, names: list[str]) -> str:
    matches = matching_brand_albums(brand, names)
    number = matches[-1].number + 1 if matches else 1
    return brand_album_name(brand, number)
