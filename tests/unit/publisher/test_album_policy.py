import pytest

from app.publisher.album_policy import (
    AlbumChoice,
    BrandAlbum,
    brand_album_name,
    choose_brand_album,
    matching_brand_albums,
    next_brand_album,
)


def test_brand_album_names_are_exact_and_zero_padded() -> None:
    assert brand_album_name("SUNON", 1) == "SUNON(01)"
    assert matching_brand_albums(
        "SUNON",
        ["SUNON(01)", "SUNON(09)", "SUNON风扇", "Delta(10)"],
    ) == (
        BrandAlbum(name="SUNON(01)", number=1),
        BrandAlbum(name="SUNON(09)", number=9),
    )


def test_album_choice_uses_latest_or_creates_first() -> None:
    assert choose_brand_album("Delta", []) == AlbumChoice(name="Delta(01)", create=True)
    assert choose_brand_album("Delta", ["Delta(01)", "Delta(03)"]) == AlbumChoice(
        name="Delta(03)", create=False
    )


def test_next_album_increments_highest_brand_number_only() -> None:
    assert next_brand_album("SUNON", ["SUNON(02)", "Delta(99)"]) == "SUNON(03)"


def test_matching_is_case_insensitive_but_does_not_accept_nearby_names() -> None:
    assert matching_brand_albums(
        "sunon",
        ["SUNON(02)", "Sunon(10)", "SUNON (11)", "SUNON(1)", "SUNON(01)-old"],
    ) == (
        BrandAlbum(name="SUNON(02)", number=2),
        BrandAlbum(name="Sunon(10)", number=10),
    )


@pytest.mark.parametrize(("brand", "number"), [("", 1), ("   ", 1), ("SUNON", 0)])
def test_album_name_rejects_empty_brand_or_non_positive_number(brand: str, number: int) -> None:
    with pytest.raises(ValueError):
        brand_album_name(brand, number)
