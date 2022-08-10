"""Request and response models for the CHESS challenge broker's APIs."""

import enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class _BrokerBase(BaseModel):
    class Config:
        # NOTE(ww): Be explicit about ignoring fields we don't yet recognize.
        extra = "ignore"

        # NOTE(ww): See Target.metadata.
        allow_population_by_field_name = True


class Challenge(_BrokerBase):
    """Represents a brokered challenge."""

    id_: str = Field(..., alias="id")
    name: str
    created_at: str


class Blob(_BrokerBase):
    """Represents a reference for a zipped blob."""

    id_: str = Field(..., alias="id")
    name: str
    created_at: str


@enum.unique
class ChallengeMetadataTargetRole(str, enum.Enum):
    """Valid CHESS metadata target roles."""

    Client = "client"
    Server = "server"


@enum.unique
class ChallengeMetadataPathType(str, enum.Enum):
    """Represents the type of a "typed" path, i.e. ``ChallengeMetadataTypedPath.type_``."""

    JavaScript = "JavaScript"
    ES5 = "ES5"
    C = "C"
    CXX = "C++"
    ELF = "ELF"


class ChallengeMetadataTypedPath(_BrokerBase):
    """Represents a "typed" path for an individual target in the CHESS challenge metadata.

    The "type" of a path indicates its expected contents, e.g. "ELF" for an ELF executable and "C"
    for source code written in C.
    """

    path: str
    container_path: str
    type_: ChallengeMetadataPathType = Field(..., alias="type")


class ChallengeMetadataTarget(_BrokerBase):
    """Represents an individual analysis target for a particular challenge.

    This "target" does **not** correspond to the ``Target`` model, either conceptually or in
    structure: a ``ChallengeMetadataTarget`` represents an individual program (either source of
    binary) that can be analyzed, while a ``Target`` represents a variant of a particular challenge
    that may have multiple ``ChallengeMetadataTarget``s within it.
    """

    name: str
    role: ChallengeMetadataTargetRole
    compose_service: str
    main_source: ChallengeMetadataTypedPath
    runtime: ChallengeMetadataTypedPath


class ChallengeMetadata(_BrokerBase):
    """Represents CHESS system metadata for a particular challenge.

    CHESS system metadata is associated with particular targets for
    each challenge within the challenge broker.

    See: https://chessconfluence.apogee-research.com/download/attachments/31195299/schema-0-5-0.json
    """

    version: str = Field(..., alias="chess_challenge_metadata")
    poller: Dict[str, str]
    targets: List[ChallengeMetadataTarget]


class Target(_BrokerBase):
    """Represents an analyzable target."""

    id_: str = Field(..., alias="id")
    created_at: str
    challenge_id: str
    parent_id: Optional[str]
    blob_id: str
    created_by: Optional[str]
    description: Optional[str]
    source_assisted: bool
    images: List[str]
    challenge_name: str
    # NOTE(ww): Different releases of the challenge broker expose
    # this as `metadata` or `metadata_`. We set `allow_population_by_field_name`
    # in the BrokerBase to accept both.
    metadata: ChallengeMetadata = Field(..., alias="metadata_")

    @property
    def compilation_image(self) -> Optional[str]:
        """Returns the name of a Docker image suitable for compiling this target, if available."""

        # HACK(ww): For the time being, the list of images supplied by the broker don't
        # have any accompanying metadata to help us select the correct one to perform
        # a compilation with. We know that the images tend with `{service}`, where
        # `{service}` looks something like `{ta}_{challenge}` for a particular TA
        # and challenge name. So, we use that as a hack to select the correct image.
        # See: https://github.com/checrs/challenge-broker/issues/25
        maybe_img = next((img for img in self.images if img.endswith(self.challenge_name)), None)
        if maybe_img is not None:
            return maybe_img

        # HACK(ww): Double hack: if the above fails, YOLO and try the first image we find.
        return next(iter(self.images), None)


class RequestedTarget(_BrokerBase):
    """Represents a "requested" target, i.e. one that's been ``POST``ed to the challenge broker and
    may or may not be in a ready state for consumption as a ``Target``."""

    id_: str = Field(..., alias="id")
    created_at: str
    challenge_id: str
    parent_id: Optional[str]
    blob_id: str
    created_by: Optional[str]
    description: Optional[str]
    source_assisted: bool
    build_log: str
    status: str
    metadata: ChallengeMetadata = Field(..., alias="metadata_")
