"""Point-of-interest (POI) analyses and their helpers."""


def initialize() -> None:
    # TODO(sm): temporarily removed OverflowableAllocations until resource use
    # can be debugged.
    # NOTE(ww): Deferred imports here to avoid circular dependencies.
    from mate.poi.analysis import (  # noqa: F401 pylint: disable=unused-import
        CommandInjection,
        IteratorInvalidation,
        PathTraversal,
        PointerDisclosure,
        TruncatedInteger,
        UninitializedStackMemory,
        UseAfterFree,
        UserStringComparisonLength,
        VariableLengthStackObject,
    )
