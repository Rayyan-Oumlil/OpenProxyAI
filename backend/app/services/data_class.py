"""Data classes, ordered from least to most sensitive. Routing (Phase 2) compares them by rank."""

from typing import Literal, get_args

DataClass = Literal["public", "internal", "confidential", "secret"]

DATA_CLASSES: tuple[DataClass, ...] = get_args(DataClass)
DEFAULT_DATA_CLASS: DataClass = "internal"


def data_class_rank(value: str) -> int:
	"""0 for public up to 3 for secret. Raises ValueError for anything else: never guess a class."""
	try:
		return DATA_CLASSES.index(value)  # type: ignore[arg-type]
	except ValueError:
		raise ValueError(f"unknown data class: {value!r}") from None
