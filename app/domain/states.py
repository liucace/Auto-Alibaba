from enum import StrEnum

from app.domain.errors import InvalidTransition


class ProductStatus(StrEnum):
    DISCOVERED = "DISCOVERED"
    FILES_STABLE = "FILES_STABLE"
    PROCESSING = "PROCESSING"
    ANALYZING = "ANALYZING"
    PAYLOAD_READY = "PAYLOAD_READY"
    FILLING = "FILLING"
    READY_TO_SAVE = "READY_TO_SAVE"
    STOPPED_BEFORE_SAVE = "STOPPED_BEFORE_SAVE"
    DRAFT_SAVING = "DRAFT_SAVING"
    DRAFT_SAVED = "DRAFT_SAVED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    FAILED = "FAILED"


_ALLOWED: dict[ProductStatus, set[ProductStatus]] = {
    ProductStatus.DISCOVERED: {ProductStatus.FILES_STABLE, ProductStatus.MANUAL_REVIEW},
    ProductStatus.FILES_STABLE: {ProductStatus.PROCESSING, ProductStatus.MANUAL_REVIEW},
    ProductStatus.PROCESSING: {ProductStatus.ANALYZING, ProductStatus.FAILED},
    ProductStatus.ANALYZING: {
        ProductStatus.PAYLOAD_READY,
        ProductStatus.MANUAL_REVIEW,
        ProductStatus.FAILED,
    },
    ProductStatus.PAYLOAD_READY: {ProductStatus.FILLING, ProductStatus.FAILED},
    ProductStatus.FILLING: {
        ProductStatus.READY_TO_SAVE,
        ProductStatus.MANUAL_REVIEW,
        ProductStatus.FAILED,
    },
    ProductStatus.READY_TO_SAVE: {
        ProductStatus.STOPPED_BEFORE_SAVE,
        ProductStatus.DRAFT_SAVING,
    },
    ProductStatus.DRAFT_SAVING: {ProductStatus.DRAFT_SAVED, ProductStatus.FAILED},
}


def transition(current: ProductStatus, target: ProductStatus) -> ProductStatus:
    if target not in _ALLOWED.get(current, set()):
        raise InvalidTransition(f"illegal task transition: {current} -> {target}")
    return target
