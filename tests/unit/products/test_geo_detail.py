import pytest
from bs4 import BeautifulSoup

from app.domain.errors import ManualReviewRequired
from app.products.geo_detail import render_geo_detail


def test_geo_detail_has_four_distinct_semantic_images() -> None:
    html = render_geo_detail(
        model="W3G630-NU33-03",
        brand="ebm-papst",
        summary="400V EC轴流风扇",
        parameters=[("额定功率", "3600W"), ("重量", "39.3kg")],
        image_urls=[f"https://example.com/{i}.jpg" for i in range(4)],
        image_roles=["整机正面", "整机背面", "电机特写", "铭牌特写"],
    )
    soup = BeautifulSoup(html, "html.parser")
    images = soup.select("img")

    assert len(images) == 4
    assert len({image["src"] for image in images}) == 4
    assert all("W3G630-NU33-03" in image.get("alt", "") for image in images)
    assert len(soup.select("[data-geo-section]")) == 8


def test_geo_detail_rejects_missing_or_duplicate_images() -> None:
    with pytest.raises(ManualReviewRequired):
        render_geo_detail(
            model="X",
            brand="B",
            summary="S",
            parameters=[],
            image_urls=["same"] * 4,
            image_roles=["a", "b", "c", "d"],
        )
