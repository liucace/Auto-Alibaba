import pytest
from pydantic import ValidationError

from app.domain.models import EvidenceValue


def test_present_value_requires_source_evidence() -> None:
    with pytest.raises(ValidationError):
        EvidenceValue[str](value="1800 g", source_page=None, source_text=None, confidence=0.9)


def test_missing_value_may_have_no_source() -> None:
    item = EvidenceValue[str](value=None, source_page=None, source_text=None, confidence=0)
    assert item.value is None
