import pytest

from app.ingest.model_number import exact_model_match, model_folder_key, normalize_model


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


def test_model_folder_key_removes_slash_without_changing_business_model() -> None:
    model = "W3G800-KS39-03/F01"

    assert normalize_model(model) == model
    assert model_folder_key(model) == "W3G800-KS39-03F01"
