import re
import unicodedata

_FULL_WIDTH_HYPHENS = str.maketrans({"－": "-", "—": "-", "–": "-", "_": "-"})


def normalize_model(raw: str) -> str:
    visible = "".join(char for char in raw if unicodedata.category(char) not in {"Cf", "Cc"})
    visible = visible.translate(_FULL_WIDTH_HYPHENS).strip().upper()
    visible = re.sub(r"[\s\u3000]+", "-", visible)
    return re.sub(r"-+", "-", visible)


def model_folder_key(raw: str) -> str:
    return normalize_model(raw).replace("/", "")


def exact_model_match(left: str, right: str) -> bool:
    return normalize_model(left) == normalize_model(right)
