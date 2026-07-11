class AutomationError(RuntimeError):
    """Base error for deterministic uploader failures."""


class InvalidTransition(AutomationError):
    """Raised when task state attempts an illegal transition."""


class ModelRowNotFound(AutomationError):
    """Raised when the exact model is absent from the inventory workbook."""


class ManualReviewRequired(AutomationError):
    """Raised when evidence or page state is unsafe to infer automatically."""
