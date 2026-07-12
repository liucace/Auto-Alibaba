import pytest

from app.publisher.playwright_port import detail_upload_is_ready


@pytest.mark.parametrize("capacity", [1, 4, 50])
def test_detail_upload_is_ready_for_one_uploaded_image(capacity: int) -> None:
    text = f"上传成功，共 1 张！\n要插入的图片(1/{capacity})\n插入图片"

    assert detail_upload_is_ready(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "要插入的图片(0/50)",
        "要插入的图片(1/50) 正在上传！",
        "要插入的图片(1/50) 准备上传！",
        "上传失败 要插入的图片(0/50)",
    ],
)
def test_detail_upload_is_not_ready_for_incomplete_state(text: str) -> None:
    assert detail_upload_is_ready(text) is False
