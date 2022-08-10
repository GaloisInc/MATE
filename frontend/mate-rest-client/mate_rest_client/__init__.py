"""Python APIs and models for interacting with MATE's REST API."""
from __future__ import annotations

import enum
import functools
import urllib.parse
from dataclasses import dataclass
from typing import Any, Dict, NewType, Optional, Protocol, Type, TypeVar

import requests
from pydantic import BaseModel

from mate_rest_client import analyses, artifacts, builds, compilations, graphs, manticore, pois

_Model = TypeVar("_Model", bound=BaseModel)


class _CurriedRequest(Protocol):
    """A typing protocol to help MyPy understand partial instance methods."""

    def __call__(self, path: str, **kwargs: Any) -> requests.Response:
        ...


class _CurriedRequestAs(Protocol):
    """A typing protocol to help MyPy understand generic partial instance methods."""

    def __call__(self, model: Type[_Model], path: str, **kwargs: Any) -> _Model:
        ...


class _CurriedRequestAsMaybe(Protocol):
    """A typing protocol to help MyPy understand generic partial instance methods."""

    def __call__(self, model: Type[_Model], path: str, **kwargs: Any) -> Optional[_Model]:
        ...


class _Method(str, enum.Enum):
    """HTTP verbs currently needed by the MATE REST API bindings."""

    GET = "GET"
    POST = "POST"
    DELETE = "DELETE"
    PUT = "PUT"
    PATCH = "PATCH"


StatusCode = NewType("StatusCode", int)
Url = NewType("Url", str)


@dataclass(frozen=True)
class RestError(Exception):
    """Raised when a request or other operation internal to the REST client fails."""

    status_code: StatusCode
    reason: str
    url: Url

    def __str__(self) -> str:
        return f"{self.status_code}: {self.reason} for {self.url}"

    @classmethod
    def from_(cls, resp: requests.Response) -> RestError:
        """Create a ``RestError`` from the given ``requests.Response``.

        Assumes that the ``request.Response`` is an error response.
        """
        return cls(StatusCode(resp.status_code), resp.reason, Url(resp.url))


@dataclass(frozen=False, init=False)
class Client:
    """The top-level Python client for MATE's REST API.

    Users can interact with subcomponents of the MATE REST API via attributes
    on any ``Client`` instance:

    - ``client.artifacts`` (``artifacts.ArtifactRoutes``): interactions with artifacts
    - ``client.builds`` (``artifacts.BuildRoutes``): interactions with builds
    - ``client.compilations`` (``artifacts.CompilationRoutes``): interactions with compilations
    - ``client.analyses`` (``artifacts.AnalysisRoutes``): interactions with analyses
    - ``client.pois`` (``artifacts.POIRoutes``): interactions with POIs
    - ``client.graphs`` (``artifacts.GraphRoutes``): interactions with graphs
    - ``client.manticore`` (``artifacts.ManticoreRoutes``): interactions with Manticore tasks

    ``Client`` instances can also make direct requests via ``Client.get()``,
    ``Client.post()``, and ``Client.delete()``. This interface should be considered
    lower-level and **not** preferred.
    """

    def __init__(self, base: str = "http://localhost:8666") -> None:
        self._base = base
        self.artifacts = artifacts.ArtifactRoutes(self)
        self.builds = builds.BuildRoutes(self)
        self.compilations = compilations.CompilationRoutes(self)
        self.analyses = analyses.AnalysisRoutes(self)
        self.pois = pois.POIRoutes(self)
        self.graphs = graphs.GraphRoutes(self)
        self.manticore = manticore.ManticoreRoutes(self)

    def _endpoint(self, path: str) -> Url:
        return Url(urllib.parse.urljoin(self._base, path))

    def _request(self, method: _Method, path: str, **kwargs: Dict[str, Any]) -> requests.Response:
        """Make a request, raising ``RestError`` on any failures.

        All keyword arguments are forwarded directly to ``requests.request()``.
        """
        url = self._endpoint(path)
        resp = requests.request(method.value, url, **kwargs)  # type: ignore[arg-type]
        if not resp.ok:
            raise RestError.from_(resp)
        return resp

    def _request_as(
        self, method: _Method, model: Type[_Model], path: str, **kwargs: Dict[str, Any]
    ) -> _Model:
        """Make a request and return the response as the given model, raising ``RestError` on any
        failures.

        All keyword arguments are forwarded directly to ``requests.request()``.
        """
        resp = self._request(method, path, **kwargs)
        return model.parse_raw(resp.text)

    def _request_as_maybe(
        self, method: _Method, model: Type[_Model], path: str, **kwargs: Dict[str, Any]
    ) -> Optional[_Model]:
        """Make a request and return the response as the given model, or ``None`` if the response is
        a 404.

        Raises ``RestError`` on any non-404 failures.

        All keyword arguments are forwarded directly to ``requests.request()``.
        """
        try:
            resp = self._request(method, path, **kwargs)
            return model.parse_raw(resp.text)
        except RestError as re:
            if re.status_code == 404:
                return None
            else:
                raise re

    get: _CurriedRequest = functools.partialmethod(_request, _Method.GET)  # type: ignore[assignment]
    post: _CurriedRequest = functools.partialmethod(_request, _Method.POST)  # type: ignore[assignment]
    delete: _CurriedRequest = functools.partialmethod(_request, _Method.DELETE)  # type: ignore[assignment]
    put: _CurriedRequest = functools.partialmethod(_request, _Method.PUT)  # type: ignore[assignment]
    patch: _CurriedRequest = functools.partialmethod(_request, _Method.PATCH)  # type: ignore[assignment]

    get_as: _CurriedRequestAs = functools.partialmethod(_request_as, _Method.GET)  # type: ignore[assignment]
    post_as: _CurriedRequestAs = functools.partialmethod(_request_as, _Method.POST)  # type: ignore[assignment]
    delete_as: _CurriedRequestAs = functools.partialmethod(_request_as, _Method.DELETE)  # type: ignore[assignment]
    put_as: _CurriedRequestAs = functools.partialmethod(_request_as, _Method.PUT)  # type: ignore[assignment]
    patch_as: _CurriedRequestAs = functools.partialmethod(_request_as, _Method.PATCH)  # type: ignore[assignment]

    get_as_maybe: _CurriedRequestAsMaybe = functools.partialmethod(_request_as_maybe, _Method.GET)  # type: ignore[assignment]
    post_as_maybe: _CurriedRequestAsMaybe = functools.partialmethod(_request_as_maybe, _Method.POST)  # type: ignore[assignment]
    delete_as_maybe: _CurriedRequestAsMaybe = functools.partialmethod(_request_as_maybe, _Method.DELETE)  # type: ignore[assignment]
    put_as_maybe: _CurriedRequestAsMaybe = functools.partialmethod(_request_as_maybe, _Method.PUT)  # type: ignore[assignment]
    patch_as_maybe: _CurriedRequestAsMaybe = functools.partialmethod(_request_as_maybe, _Method.PATCH)  # type: ignore[assignment]
