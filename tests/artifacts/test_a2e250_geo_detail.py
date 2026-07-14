from pathlib import Path

from app.products.detail_policy import load_detail_policy

ROOT = Path(__file__).resolve().parents[2]


def test_detail_policy_requires_fixed_company_tail_after_product_sections() -> None:
    policy = load_detail_policy()

    assert policy.sections == (
        "entity_answer",
        "quick_facts",
        "core_parameters",
        "operating_points",
        "product_images",
        "dimensions_installation",
        "materials_electrical_environment",
        "purchase_confirmation",
        "faq",
        "company",
    )
    assert policy.sections[-1] == "company"
    assert policy.current_product_image_count == 4
    assert len(policy.company_image_urls) == 6


def test_detail_policy_preserves_editor_sync_guards() -> None:
    config = (ROOT / "config" / "detail_templates.yaml").read_text(encoding="utf-8")

    assert "form_model_sync: updateModelValue" in config
    assert "quality_payload_must_not_be_null: true" in config
