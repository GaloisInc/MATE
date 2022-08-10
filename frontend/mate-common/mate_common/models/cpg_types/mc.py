from pydantic import BaseModel


class MachineFrameInfo(BaseModel):
    """Models the information available for a ``MachineFunction``'s stack frame."""

    has_stack_objects: bool
    """
    Whether or not this frame contains stack objects.
    """

    has_variadic_objects: bool
    """
    Whether or not some (or all) of the objects in this stack frame are variadic.
    """

    is_frame_address_taken: bool
    """
    Whether a call to ``llvm.frameaddress`` occurs in this frame's function.
    """

    is_return_address_taken: bool
    """
    Whether a call to ``llvm.returnaddress`` occurs in this frame's function.
    """

    num_objects: int
    """
    The number of stack objects in this frame.
    """

    num_fixed_objects: int
    """
    The number of fixed (i.e., non-variadic) stack objects in this frame.
    """

    stack_size: int
    """
    The size of this stack frame (i.e., for all fixed objects), in bytes.
    """

    adjusts_stack: bool
    """
    Whether or not this frame's function adjusts the stack.
    """
