"""A base class for declarative mapping, with extra functionality.

See https://docs.sqlalchemy.org/en/13/orm/extensions/declarative/mixins.html#augmenting-the-base
"""

from __future__ import annotations

import enum
from threading import local
from typing import TYPE_CHECKING, Any, Type, TypeVar

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.hybrid import hybrid_method
from sqlalchemy.orm import sessionmaker
from sqlalchemy.types import Enum as SAEnum
from sqlalchemy.types import String

from mate_query.cpg.models._typechecking import HasDynamicAttributes

T = TypeVar("T", bound="Base")

_VALUES_CALLABLE = lambda x: [e.value for e in x]


def enum_column(name: str, klass: Type[enum.Enum]) -> Column:
    """Create an enum column named ``name`` from the given ``enum.Enum`` subclass."""
    return Column(
        name,
        SAEnum(klass, values_callable=_VALUES_CALLABLE, validate_strings=True, index=True),
        nullable=False,
    )


def uuid_column() -> Column:
    return Column("uuid", String, primary_key=True, index=True)


if TYPE_CHECKING:

    # NOTE(lb): It's unclear to me why simply importing this exact definition from
    # _typechecking will result in a type error ("error: Invalid metaclass
    # 'ClassHasDynamicAttributes'"). Mypy bug?
    class ClassHasDynamicAttributes(type, HasDynamicAttributes):
        pass

else:

    ClassHasDynamicAttributes = type


class Base(HasDynamicAttributes, metaclass=ClassHasDynamicAttributes):
    uuid = uuid_column()
    attributes = Column(JSONB, nullable=False)
    local: Any = None

    @classmethod
    def _session(cls) -> Any:
        return sessionmaker(bind=cls.local.bind)()

    @classmethod
    def find_by(cls: Type[T], **kwargs: Any) -> T:
        return cls._session().query(cls).filter_by(**kwargs).one()

    @classmethod
    def from_uuid(cls: Type[T], uuid: str) -> T:
        return cls.find_by(uuid=uuid)

    @hybrid_method
    def __eq__(self: T, other: T) -> bool:
        return self.uuid == other.uuid

    @hybrid_method
    def __hash__(self) -> int:
        return hash(self.uuid)


Base.local = local()
