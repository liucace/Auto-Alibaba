import pytest

from app.domain.errors import InvalidTransition
from app.domain.states import ProductStatus, transition


def test_saved_draft_is_terminal() -> None:
    assert (
        transition(ProductStatus.DRAFT_SAVING, ProductStatus.DRAFT_SAVED)
        is ProductStatus.DRAFT_SAVED
    )
    with pytest.raises(InvalidTransition):
        transition(ProductStatus.DRAFT_SAVED, ProductStatus.PROCESSING)


def test_ready_to_save_can_only_stop_or_save() -> None:
    assert (
        transition(ProductStatus.READY_TO_SAVE, ProductStatus.STOPPED_BEFORE_SAVE)
        is ProductStatus.STOPPED_BEFORE_SAVE
    )
