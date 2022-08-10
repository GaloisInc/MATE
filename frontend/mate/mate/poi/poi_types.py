"""This module defines the types that are subtyped by all POI Analysis implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, Final, List, NewType, Tuple, Type

import markdown

from mate_common.models.analyses import POI, AnalysisInfo
from mate_common.models.graphs import GraphServerRequest

if TYPE_CHECKING:
    from typing import Iterable

    from mate_query.db import Graph as CPG
    from mate_query.db import Session


_DEFAULT_BACKGROUND_TEMPLATE: Final[
    str
] = """
A POI analysis named {name} has been registered, but doesn't have an analysis background to display.

This is a *minor* programming error; the analysis class should be corrected to
contain a Markdown-formatted `_background` that adequately explains the analysis.
"""

HTML = NewType("HTML", str)

POIGraphsPair = Tuple[POI, List[GraphServerRequest]]

_analysis_registry: Dict[str, Type[Analysis]] = {}


class Analysis(ABC):
    """Abstract base class for Analyses."""

    @classmethod
    @property
    def _background(cls) -> str:
        return _DEFAULT_BACKGROUND_TEMPLATE.format(name=cls.__name__)

    def __init_subclass__(cls, *args: Any, **kwargs: Any) -> None:
        super().__init_subclass__(*args, **kwargs)
        # Record each subclass as it's initialized. We'll use this registry
        # to look up POI analyses by name when running them on CPG builds.
        _analysis_registry[cls.__name__] = cls

    @abstractmethod
    def run(self, session: Session, cpg: CPG, inputs: Dict[str, Any]) -> Iterable[POIGraphsPair]:
        pass

    @staticmethod
    def iter_analyses() -> Iterable[Tuple[str, Type[Analysis]]]:
        return _analysis_registry.items()

    @staticmethod
    def by_name(name: str) -> Type[Analysis]:
        """Given an analysis name (e.g., ``"UseAfterFree"``, return the corresponding ``Analysis``
        subclass)."""
        return _analysis_registry[name]

    @classmethod
    def background(cls) -> HTML:
        """Return an HTML-formatted background explanation for this analysis."""
        background = getattr(
            cls,
            "_background",
        )
        return HTML(markdown.markdown(background))

    @classmethod
    def to_info(cls) -> AnalysisInfo:
        return AnalysisInfo(
            name=cls.__name__,
            background=cls.background(),
        )
