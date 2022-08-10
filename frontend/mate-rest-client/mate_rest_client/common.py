"""Common classes and routines for MATE's REST client."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Protocol

from pydantic import BaseModel

if TYPE_CHECKING:
    import mate_rest_client


class Routes:
    """A management wrapper for a group of related REST endpoints."""

    def __init__(self, client: mate_rest_client.Client) -> None:
        self._client = client


class _HasInfo(Protocol):
    """A typing protocol for objects that have a backing Pydantic ``BaseModel``."""

    _info: BaseModel


class APIModel(_HasInfo):
    """Common functionality for all models returned by the REST API wrapper."""

    def dict(self) -> Dict[str, Any]:
        return self._info.dict()

    def json(self, *args: str, **kwargs: Any) -> str:
        pretty = kwargs.pop("pretty", False)
        if pretty:
            kwargs["sort_keys"] = True
            kwargs["indent"] = 4
        return self._info.json(*args, **kwargs)
