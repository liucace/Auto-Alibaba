import pytest

from app.domain.errors import ManualReviewRequired
from app.domain.models import OperatingPoint
from app.products.specification_policy import materialize_platform_specification


def test_materializes_50_60hz_slash_values_and_cfm_conversion() -> None:
    points = (
        OperatingPoint(
            frequency_hz=50,
            speed_rpm=2150,
            airflow_cfm=66,
            static_pressure_in_h2o=0.14,
            current_a=0.09,
            power_w=18,
            noise_db_a=44,
        ),
        OperatingPoint(
            frequency_hz=60,
            speed_rpm=2500,
            airflow_cfm=80,
            static_pressure_in_h2o=0.17,
            current_a=0.09,
            power_w=16.5,
            noise_db_a=48,
        ),
    )

    specification, enriched = materialize_platform_specification(
        {"规格型号": "DP201AT-2122HBL.GN", "风叶直径_m": 0.119},
        points,
    )

    assert specification["电机功率_w"] == "18/16.5"
    assert specification["转速_rpm"] == "2150/2500"
    assert specification["风量_m3h"] == "112.1/135.9"
    assert specification["电流_a"] == "0.09/0.09"
    assert [point.airflow_m3h for point in enriched] == [112.1, 135.9]


def test_rejects_platform_value_that_conflicts_with_operating_points() -> None:
    points = (OperatingPoint(frequency_hz=50, airflow_cfm=66),)

    with pytest.raises(ManualReviewRequired, match="风量_m3h"):
        materialize_platform_specification({"风量_m3h": "999"}, points)


def test_sorts_operating_points_before_materializing_slash_values() -> None:
    points = (
        OperatingPoint(frequency_hz=60, speed_rpm=2500),
        OperatingPoint(frequency_hz=50, speed_rpm=2150),
    )

    specification, enriched = materialize_platform_specification({}, points)

    assert specification["转速_rpm"] == "2150/2500"
    assert [point.frequency_hz for point in enriched] == [50, 60]


def test_rejects_duplicate_operating_point_frequencies() -> None:
    points = (
        OperatingPoint(frequency_hz=50, speed_rpm=2150),
        OperatingPoint(frequency_hz=50, speed_rpm=2500),
    )

    with pytest.raises(ManualReviewRequired, match="frequencies must be unique"):
        materialize_platform_specification({}, points)
