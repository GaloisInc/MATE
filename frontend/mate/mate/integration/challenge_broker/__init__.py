"""Wrappers for the CHESS challenge broker's REST API endpoints."""

from __future__ import annotations

import urllib.parse as urlparse
import uuid
from pathlib import Path
from typing import BinaryIO, List, Optional

import requests

from mate.config import CHALLENGE_BROKER_BASE
from mate_common.error import MateError
from mate_common.models.challenge_broker import Blob, Challenge, RequestedTarget, Target


class BrokerError(MateError):
    """Raised whenever an unrecoverable error during challenge broker interaction occurs."""

    pass


class Client:
    """A client for the CHESS challenge broker's REST API.

    MATE APIs that interact with the challenge broker should use :attr:`client`.
    """

    def __init__(self, base: Optional[str] = None):
        if base is None:
            self._base = CHALLENGE_BROKER_BASE
        else:
            self._base = base

    def challenges(self) -> List[Challenge]:
        """Returns the challenges that are currently available on the broker.

        Raises ``BrokerError`` if the request fails.
        """
        endpoint = urlparse.urljoin(self._base, "/v1/challenges")
        resp = requests.get(endpoint)
        if not resp.ok:
            raise BrokerError(f"challenge broker failed to list challenges: {resp!r}")
        return [Challenge(**c) for c in resp.json()]

    def challenge_by_id(self, id_: str) -> Optional[Challenge]:
        """Returns a challenge by ID, if present."""
        endpoint = urlparse.urljoin(self._base, f"/v1/challenges/{id_}")
        resp = requests.get(endpoint)
        if not resp.ok:
            return None
        return Challenge(**resp.json())

    def challenge_by_name(self, name: str) -> Optional[Challenge]:
        """Returns a challenge by name, if present.

        Raises ``BrokerError`` if the underlying request fails.
        """
        # NOTE(ww): The broker doesn't provide a convenience endpoint for
        # names, so we have to filter over every challenge to filter by name.
        return next((c for c in self.challenges() if c.name == name), None)

    def create_target(
        self,
        challenge: Challenge,
        blob: Blob,
        *,
        source_assisted: bool = False,
        description: Optional[str] = None,
        parent_id: Optional[str] = None,
    ) -> RequestedTarget:
        """Create a new target, by way of the "requested targets" API."""

        # NOTE(ww): The requested targets API isn't documented.
        payload = {
            "id": str(uuid.uuid4()),
            "challenge_id": challenge.id_,
            "blob_id": blob.id_,
            "description": description,
            "parent_id": parent_id,
            "source_assisted": source_assisted,
        }

        endpoint = urlparse.urljoin(self._base, "/v1/requested_targets")
        resp = requests.post(endpoint, json=payload)
        if not resp.ok:
            raise BrokerError(f"target creation endpoint failed: {resp!r}")

        return RequestedTarget(**resp.json())

    def targets(self, *, for_: Optional[Challenge] = None) -> List[Target]:
        """Returns the targets that are currently available on the broker."""
        endpoint = urlparse.urljoin(self._base, "/v1/targets")
        params = {}
        if for_ is not None:
            params["challenge_id"] = for_.id_
        resp = requests.get(endpoint, params=params)

        if not resp.ok:
            raise BrokerError(f"challenge broker failed to list targets: {resp!r}")

        return [Target(**t) for t in resp.json()]

    def target_by_id(self, id_: str) -> Optional[Target]:
        """Returns a target by ID, if present."""
        endpoint = urlparse.urljoin(self._base, f"/v1/targets/{id_}")
        resp = requests.get(endpoint)
        if not resp.ok:
            return None
        return Target(**resp.json())

    def root_target(self, *, for_: Challenge) -> Optional[Target]:
        """Returns the root target for a challenge, if present."""

        # NOTE(ww): The challenge broker should really always guarantee that
        # every challenge has exactly one root target, but I don't believe
        # they're currently enforcing that. So our signature includes
        # the possibility that no root target is found.

        return next((t for t in self.targets(for_=for_) if t.parent_id is None), None)

    def create_blob(self, filename: Path) -> Blob:
        """Create a new blob, populating it with the contents of the given file."""
        endpoint = urlparse.urljoin(self._base, f"/v1/blobs")
        with filename.open("rb") as io:
            resp = requests.post(endpoint, files={filename: io})

        if not resp.ok:
            raise BrokerError(f"blob creation endpoint failed: {resp!r}")

        return Blob(**resp.json()[0])

    def root_blob(self, *, for_: Challenge) -> Optional[Blob]:
        """Returns the blob associated with the root target for a challenge, if present."""
        target = self.root_target(for_=for_)
        if target is None:
            return None

        return self.blob_by_id(target.blob_id)

    def blobs(self) -> List[Blob]:
        """Returns the blobs that are currently available on the broker."""
        endpoint = urlparse.urljoin(self._base, "/v1/blobs")
        resp = requests.get(endpoint)
        return [Blob(**b) for b in resp.json()]

    def blob_by_id(self, id_: str) -> Optional[Blob]:
        """Returns a blob by ID, if present."""
        endpoint = urlparse.urljoin(self._base, f"/v1/blobs/{id_}")
        resp = requests.get(endpoint)
        if not resp.ok:
            return None
        return Blob(**resp.json())

    def blob_data_by_id(self, id_: str) -> Optional[BinaryIO]:
        """Return a fileobj containing the contents of the blob referenced by the given ID."""
        endpoint = urlparse.urljoin(self._base, f"/v1/blobs/{id_}/data")
        resp = requests.get(endpoint, stream=True)
        if not resp.ok:
            return None
        return resp.raw

    def blob_data(self, blob: Blob) -> Optional[BinaryIO]:
        """Return a fileobj containing the contents of the given blob."""
        return self.blob_data_by_id(blob.id_)
