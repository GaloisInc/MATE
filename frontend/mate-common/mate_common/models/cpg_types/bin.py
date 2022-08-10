from pydantic import BaseModel, Field


class UsedRegister(BaseModel):
    """A symbolic representation of an ``ASMInst``'s use of a register, including how that register
    is used."""

    # NOTE(ww): `register` is an implementation attribute; use an alias instead.
    register_: str = Field(alias="register")
    access: str


class UsedMemory(BaseModel):
    """A symbolic representation of an ``ASMInst``'s use of a memory location, including how that
    memory is used."""

    segment: str
    base: str
    index: str
    scale: int
    displacement: int
    memory_size: int
    access: str
    vsib_size: int
