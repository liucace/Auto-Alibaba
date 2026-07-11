from app.publisher.playwright_port import value_matches


def test_exact_values_are_skipped_on_resume() -> None:
    assert value_matches("400", "400")
    assert not value_matches("", "400")


def test_platform_material_label_matches_pp_value() -> None:
    assert value_matches("ABS塑料 PP塑料", "PP塑料", contains=True)
