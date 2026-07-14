from collections.abc import Callable

from app.domain.errors import ManualReviewRequired
from app.domain.models import OperatingPoint

CFM_TO_M3H = 1.699


def _number(value: float) -> str:
    return f"{value:g}"


def _slash(
    points: tuple[OperatingPoint, ...],
    getter: Callable[[OperatingPoint], float | None],
) -> str | None:
    values = [getter(point) for point in points]
    if not values or any(value is None for value in values):
        return None
    return "/".join(_number(float(value)) for value in values if value is not None)


def _set_or_verify(
    specification: dict[str, str | int | float], key: str, expected: str | None
) -> None:
    if expected is None:
        return
    existing = str(specification.get(key, "")).strip()
    if existing and existing != expected:
        raise ManualReviewRequired(f"platform specification conflicts with operating points: {key}")
    specification[key] = expected


def materialize_platform_specification(
    raw: dict[str, str | int | float],
    operating_points: tuple[OperatingPoint, ...],
) -> tuple[dict[str, str | int | float], tuple[OperatingPoint, ...]]:
    ordered = tuple(sorted(operating_points, key=lambda point: point.frequency_hz))
    if len({point.frequency_hz for point in ordered}) != len(ordered):
        raise ManualReviewRequired("operating point frequencies must be unique")
    enriched = tuple(
        point.model_copy(update={"airflow_m3h": round(point.airflow_cfm * CFM_TO_M3H, 1)})
        if point.airflow_cfm is not None and point.airflow_m3h is None
        else point
        for point in ordered
    )
    specification = dict(raw)
    _set_or_verify(specification, "电机功率_w", _slash(enriched, lambda p: p.power_w))
    _set_or_verify(specification, "转速_rpm", _slash(enriched, lambda p: p.speed_rpm))
    _set_or_verify(specification, "风量_m3h", _slash(enriched, lambda p: p.airflow_m3h))
    _set_or_verify(specification, "电流_a", _slash(enriched, lambda p: p.current_a))
    return specification, enriched
