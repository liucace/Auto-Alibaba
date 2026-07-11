import pytest

from app.ingest.model_number import exact_model_match, normalize_model


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (" A2E250-AL06-01\u200b", "A2E250-AL06-01"),
        ("a2e250_al06_01", "A2E250-AL06-01"),
        ("A2E250　AL06－01", "A2E250-AL06-01"),
    ],
)
def test_normalize_model(raw: str, expected: str) -> None:
    assert normalize_model(raw) == expected


def test_similar_models_are_never_equal() -> None:
    assert not exact_model_match("A2E250-AL06-01", "A2E250-AL06-10")
    assert not exact_model_match("A2E250-AL06-O1", "A2E250-AL06-01")
