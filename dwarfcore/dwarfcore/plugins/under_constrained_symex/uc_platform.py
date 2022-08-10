import itertools
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from manticore.core.smtlib import (
    ArrayVariable,
    BitVecConstant,
    BitVecITE,
    BitVecVariable,
    BoolVariable,
    Constant,
    ConstraintSet,
    Expression,
    Operators,
    SelectedSolver,
    get_taints,
    issymbolic,
    pretty_print,
    replace,
    simplify,
)
from manticore.core.state import Concretize
from manticore.native.cpu.cpufactory import CpuFactory
from manticore.native.memory import SMemory64
from manticore.platforms.linux import SLinux

from mate_common.models.integration import UnboundedPtrPolicy, UnboundedPtrPolicyType
from mate_query.cpg.models import DWARFType

from .dwarf_helper import *
from .errors import ErrorManager
from .exceptions import *
from .logging import logger
from .smt import SmtNameTranslator
from .user_constraints import Metavar, UserConstraintManager

# TODO(boyan): have a cleaner way to get the DB session/graph
# Globals because they are not serialisable as part of the state :(
_UCSE_session: Any = None
_UCSE_graph: Any = None


def expr_to_data(expr: Expression):
    """Transform an expression to a list of bytes."""
    data = [Operators.CHR(Operators.EXTRACT(expr, off, 8)) for off in range(0, expr.size, 8)]
    return data


def get_write_value_size(value):
    """Get the size in bytes of a value.

    :param value: can be bytes or bitvector
    """
    try:
        value_size = len(value)
    except TypeError:  #  Assume BitVec
        value_size = value.size // 8
    return value_size


class MemObject(SMemory64):
    """This class represents an unconstrained object allocated somewhere in memory."""

    def __init__(
        self, uid: int, content_type_size: int, size: int = 0, name: str = "", *args, **kwargs
    ):
        """
        :param uid: Unique object identifier
        :param content_type_size: The size in bytes of the type contained in the object.
        If the object is an array, this is the size of ONE array element. If the object is
        a single instance, this is the total object size
        :param size: Size of the object in memory, in bytes
        :param name: Optional name for the object
        """
        super().__init__(*args, **kwargs)
        self.uid = uid
        self.size = size
        self.content_type_size = content_type_size
        self.name = name

    def __reduce__(self):
        return (
            self.__class__,
            (
                self.uid,
                self.content_type_size,
                self.size,
                self.name,
                self.constraints,
                self._symbols,
                self._maps,
            ),
        )

    def init(self, content: List[Expression]):
        """Fill the memory object with its content.

        Should be called only once, it is separated from the __init__ constructor to make pickling
        easier
        """
        self.size = sum([e.size for e in content]) // 8
        self.mmap(0, self.size, "rw")
        offset = 0
        debug_msg = "Creating object with expressions: "
        for expr in content:
            debug_msg += "     " + f"(size {expr.size}) " + pretty_print(expr)
            self.write(offset, expr_to_data(expr), self.constraints)
            offset += expr.size // 8
        logger.debug(debug_msg)
        assert self.size == offset
        assert self.size % self.content_type_size == 0

    def _try_get_solutions(self, address, size, access, _max_solutions=0x1000, force=False):
        """Wrapper around the parent class method to constrain the max_solutions to the object size
        when reading from a symbolic offset."""
        assert self.size >= size
        max_sol = self.size - size
        return super()._try_get_solutions(address, size, access, max_sol, force)

    def read(self, offset, size, constr: ConstraintSet):
        """Read 'size' bits at 'offset' in the object.

        :param offset: offset of the read within the object, in bytes
        :param size: number of bits to read
        :param constr: symbolic constraints
        """
        self.constraints = constr
        # Assert that the object is big enough to read 'size' bytes from it
        assert self.size >= size
        res = super().read(offset, size)
        return res

    def write(self, offset, value, constr: ConstraintSet):
        """Write 'value' at 'offset' in the object.

        :param offset: offset of the write within the object, in bytes
        :param value: the value to write
        :param constr: symbolic constraints
        """
        self.constraints = constr
        value_size = get_write_value_size(value)
        # Assert that the object is big enough to write the value to it
        assert self.size >= value_size
        return super().write(offset, value)


class GetTaints:
    """Custom visitor to get expression taints but discard taints in ITE conditions."""

    def __init__(self, regex=None):
        self.taints = set()
        self.regex = regex

    def visit(self, expression):
        if isinstance(expression, BitVecITE):
            #  Skip condition in operands[0]
            self.visit(expression.operands[1])
            self.visit(expression.operands[2])
        elif (
            isinstance(expression, BitVecVariable)
            or isinstance(expression, BoolVariable)
            or isinstance(expression, ArrayVariable)
        ):
            for taint in get_taints(expression, self.regex):
                self.taints.add(taint)
        elif hasattr(expression, "operands"):
            for op in expression.operands:
                self.visit(op)

    @property
    def result(self):
        return list(self.taints)


def get_expr_bases(expr: Expression):
    visitor = GetTaints("base.*")
    visitor.visit(expr)
    return visitor.result


def has_base(expr: Expression) -> bool:
    return len(get_expr_bases(expr)) > 0


class UCMemory64(SMemory64):
    """Wrapper around regular memory that automatically dispatches memory accesses between the stock
    memory and the UC memory manager.

    It is also responsible for populating the UC memory on-the-fly when new objects are accessed
    """

    def __init__(
        self,
        constraints: Optional[ConstraintSet] = None,
        symbols=None,
        *args,
        **kwargs,
    ):
        if constraints is None:
            constraints = ConstraintSet()
        super().__init__(constraints, symbols, *args, **kwargs)

        # Those are set by the UCSE plugin when the state is loaded
        self.error_manager: Optional[ErrorManager] = None
        self.user_constraints: Optional[UserConstraintManager] = None
        self.native_array_size_policy: UnboundedPtrPolicy = UnboundedPtrPolicy(
            policy_type=UnboundedPtrPolicyType.DEFAULT
        )
        self.complex_array_size_policy: UnboundedPtrPolicy = UnboundedPtrPolicy(
            policy_type=UnboundedPtrPolicyType.DEFAULT
        )

        ## Initialise underconstrained memory
        # Maps a 'base' to an allocated MemObject
        self.base_to_object: Dict[str, MemObject] = {}
        # Maps a 'base' to a type if the MemObject itself hasn't been allocated
        self.base_to_type: Dict[str, Any] = {}
        # Maps a 'base' to the type of the *pointer* to the object
        self.base_to_ptr_type: Dict[str, Any] = {}
        # Maps a 'base' to its bitvector
        self.base_to_bitvec: Dict[str, Expression] = {}
        # Maps a 'base' to its meta-variable bitvecs ($LEN, $CAPACITY, $SIZE, etc)
        self.base_to_metavars: Dict[str, Dict[Metavar, Expression]] = {}
        # Maps a 'base' to its concretized metavars
        self.base_to_metavar_values: Dict[Metavar, Dict[str, int]] = {
            Metavar.LEN: {},
            Metavar.SIZE: {},
            Metavar.CAPACITY: {},
        }

        # Maps a variable name to a base
        self.name_to_base: Dict[str, str] = {}

        # Note: we don't make those static because this class needs to be
        # serializable
        self._data_cnt = 0  # Static count for new symbolic data expressions
        self._base_cnt = 0  # Static count for new objects

    def __reduce__(self):
        return (
            self.__class__,
            (self.constraints, self._symbols, self._maps, self.cpu),
            {
                "base_to_object": self.base_to_object,
                "base_to_type": self.base_to_type,
                "base_to_ptr_type": self.base_to_ptr_type,
                "base_to_bitvec": self.base_to_bitvec,
                "base_to_metavars": self.base_to_metavars,
                "base_to_metavar_values": self.base_to_metavar_values,
                "name_to_base": self.name_to_base,
                "data_cnt": self._data_cnt,
                "base_cnt": self._base_cnt,
            },
        )

    def __setstate__(self, s):
        self.base_to_object = s["base_to_object"]
        self.base_to_type = s["base_to_type"]
        self.base_to_ptr_type = s["base_to_ptr_type"]
        self.base_to_bitvec = s["base_to_bitvec"]
        self.base_to_metavars = s["base_to_metavars"]
        self.base_to_metavar_values = s["base_to_metavar_values"]
        self.name_to_base = s["name_to_base"]
        self._data_cnt = s["data_cnt"]
        self._base_cnt = s["base_cnt"]

    def check_oob_access(self, address, size, access, fix_oob=False):
        """Check if a memory access to an underconstrained memory object can be out of bounds. If
        the access can be out of bounds, an error is recorded in the error manager. If fix_oob is
        True, the method tries to add constraints to enforce the access to be valid. Otherwise a
        FatalSymexError exception is raised.

        :param access: either "read" or "write"
        :param address: memory address that is accessed
        :param size: number of bytes to read/write
        :param fix_oob: if set to True and if offset can be out of bounds, try to add a constraint to the
         constraint set such that to enforce 'offset' to be in within the bounds of 'obj'
        """
        address = simplify(address)
        if issymbolic(address) and has_base(address):
            # Get pointer base
            base = self.uc_get_base_from_expr(address)
            # Check whether this object has been created before
            if not self.uc_base_has_object(base):
                obj = self.uc_new_object_for_base(base)
            else:
                obj = self.uc_get_object_for_base(base)
            # Get read offset
            offset = self.uc_get_offset_from_expr(address)
            # OOB checks
            if not self.error_manager is None:
                self.error_manager.check_oob_access(
                    access, obj, offset, size, self, self.cpu.PC, fix_oob
                )

    def read(self, address, size, force=False):
        """Memory read.

        If 'address' points to an underconstrained object, it is assumed that the access has been
        validated by a prior call to check_oob_access()
        """
        address = simplify(address)
        if issymbolic(address) and has_base(address):
            # Get pointer base
            base = self.uc_get_base_from_expr(address)
            #  Check whether this object has been created before
            # NOTE: this assumes that check_oob_access() has been
            #  called to check the address expression
            obj = self.uc_get_object_for_base(base)
            # Get read offset
            offset = self.uc_get_offset_from_expr(address)
            # Perform read
            return obj.read(offset, size, self.constraints)
        else:
            return super().read(address, size, force)

    def write(self, address, value, force=False):
        """Memory write.

        If 'address' points to an underconstrained object, it is assumed that the access has been
        validated by a prior call to check_oob_access()
        """
        address = simplify(address)
        if issymbolic(address) and has_base(address):
            # Get pointer base
            base = self.uc_get_base_from_expr(address)
            #  Get the object
            # NOTE: this assumes that check_oob_access() has been
            #  called to check the address expression
            obj = self.uc_get_object_for_base(base)
            # Get write offset
            offset = self.uc_get_offset_from_expr(address)
            # Perform write
            return obj.write(offset, value, self.constraints)
        else:
            return super().write(address, value, force)

    ### Underconstrained memory methods
    def uc_get_dwarf_type_by_uuid(self, type_uuid, resolve_base: bool = False) -> DWARFType:
        # Get DWARF type
        dwarf_type = _UCSE_session.query(_UCSE_graph.DWARFType).filter_by(uuid=type_uuid).one()
        if resolve_base:
            dwarf_type = dwarf_get_base_type(dwarf_type)
        return dwarf_type

    def uc_get_new_base(self) -> str:
        self._base_cnt += 1
        return str(self._base_cnt - 1)

    def uc_get_base_from_expr(self, expr: Expression) -> str:
        """Extract the 'base' component of a pointer expression."""
        taints = get_expr_bases(expr)
        if len(taints) > 1:
            raise BaseNotUniqueException(f"Base not unique in expression {pretty_print(expr)}")
        elif len(taints) == 0:
            raise NoBaseException(f"No base in expression {pretty_print(expr)}")
        else:
            return taints[0].split(".")[1]

    def uc_get_offset_from_expr(self, expr: Expression) -> Union[Expression, int]:
        """Extract the 'offset' component of a pointer expression."""
        #  First get the base
        base = self.uc_get_base_from_expr(expr)
        base = self.base_to_bitvec[base]
        # Then compute the offset
        offset = simplify(expr - base)
        # If offset is constant, return it
        if isinstance(offset, Constant):
            return offset.value
        # If offset is complex, check that the pointer can still be expressed as: ptr = base + offset
        self.uc_check_pointer_offset_integrity(base, offset)
        return offset

    def uc_check_pointer_offset_integrity(self, base: Expression, offset: Expression):
        """Check that offset is a valid offset expression for a given base."""
        with self.constraints as constraints:
            base2 = constraints.new_bitvec(size=base.size)
            offset2 = replace(offset, {base: base2})
            # if the offset expression can taken different values when the base pointer value
            # changes, it means that the expression is too complex and can't be expressed as
            # base + offset
            offset_constraint = offset != offset2

            # Also duplicate constraints related to the offset and replace 'base'
            # with 'base2' in them.
            constraints = constraints.related_to(offset_constraint)
            for c in constraints.related_to(base):
                constraints.add(replace(c, {base: base2}))

            if SelectedSolver.instance().can_be_true(constraints, offset_constraint):
                raise ExpressionTooComplexException(
                    f"Under-constrained offset too complex: {pretty_print(offset)}"
                )
            return
        raise Exception(
            "uc_check_pointer_integrity(): failed to use ConstraintSet in context statement"
        )

    def uc_get_new_data_expr(self, size: int, name: str) -> Expression:
        """Generate a new abstract expression representing unconstrained data.

        :param size: Size in bits
        """
        self._data_cnt += 1
        name = SmtNameTranslator.make_name_smt_compliant(name)
        res = self.constraints.new_bitvec(size, name=name)
        if not self.user_constraints is None:
            self.user_constraints.apply_constraints(self.constraints, name)
        return res

    def uc_get_metavar_from_object_name(self, metavar: Metavar, obj_name: str) -> str:
        """Return the variable name for a given meta-variable of object named 'obj_name'."""
        if metavar is Metavar.LEN:
            tmp = f"{UserConstraintManager._LEN_OP}({obj_name})"
        elif metavar is Metavar.CAPACITY:
            tmp = f"{UserConstraintManager._CAPACITY_OP}({obj_name})"
        elif metavar is Metavar.SIZE:
            tmp = f"{UserConstraintManager._SIZE_OP}({obj_name})"
        else:
            raise UCException(f"Not implemented for metavar: {metavar}")
        return SmtNameTranslator.make_name_smt_compliant(tmp)

    def uc_get_new_base_expr(self, ptr_type_uuid, type_uuid, name: str) -> Expression:
        """Generate a new abstract expression representing an unconstrained pointer."""
        # Necessary to pass linting checks
        if self.user_constraints is None:
            raise UCException("uc_get_new_base_expr(): user_constraints is None!")

        # Get canonical names for new object and its meta-variables
        name = SmtNameTranslator.make_name_smt_compliant(name)
        array_len_name = self.uc_get_metavar_from_object_name(Metavar.LEN, name)
        capacity_name = self.uc_get_metavar_from_object_name(Metavar.CAPACITY, name)
        size_name = self.uc_get_metavar_from_object_name(Metavar.SIZE, name)

        # Checks if constrained to point within another variable
        base: Optional[str] = None
        if self.user_constraints.points_within_other_variable(name):
            # Consume the $POINTS_WITHIN constraint
            pointed_var = self.user_constraints.get_points_within_destination(name)
            # Give a base to the pointed variable if it wasn't created yet
            if not pointed_var in self.name_to_base:
                self.name_to_base[pointed_var] = self.uc_get_new_base()
            # Get pointed_var taint
            base = self.name_to_base[pointed_var]
            taint = f"base.{base}"
            # Create variable
            res = self.constraints.new_bitvec(self.memory_bit_size, name=name, taint=(taint,))
        else:
            # Generate new base. If that name already had a dedicated base
            # then use it, else create a new base
            base = self.name_to_base.get(name, None)
            if base is None:
                base = self.uc_get_new_base()
                self.name_to_base[name] = base
            taint = f"base.{base}"
            # Add the type of object pointed by this base.
            # The actual MemObject will be created when the pointer is
            # first dereferenced
            self.base_to_type[base] = type_uuid
            self.base_to_ptr_type[base] = ptr_type_uuid
            res = self.constraints.new_bitvec(self.memory_bit_size, name=name, taint=(taint,))
            self.base_to_bitvec[base] = res

            metavars_dict = {
                Metavar.LEN: self.constraints.new_bitvec(self.memory_bit_size, name=array_len_name),
                Metavar.CAPACITY: self.constraints.new_bitvec(
                    self.memory_bit_size, name=capacity_name
                ),
                Metavar.SIZE: self.constraints.new_bitvec(self.memory_bit_size, name=size_name),
            }
            self.base_to_metavars[base] = metavars_dict

        # Add user defined constraints related to this object
        self.user_constraints.apply_class_constraints(
            f"{name}->", dwarf_get_base_type(self.uc_get_dwarf_type_by_uuid(type_uuid))
        )

        # Apply user constraints on object and meta-variables
        self.user_constraints.apply_constraints(self.constraints, name)
        self.user_constraints.apply_constraints(self.constraints, array_len_name)
        self.user_constraints.apply_constraints(self.constraints, capacity_name)
        self.user_constraints.apply_constraints(self.constraints, size_name)

        return res

    def uc_func_arg_to_expr(self, arg) -> Expression:
        """Translates an underconstrained function argument to a smt expression to be assigned to
        the corresponding register."""
        dwarf_type = dwarf_get_base_type(arg.dwarf_type)
        if dwarf_is_pointer_or_reference_type(dwarf_type):
            pointed_type_uuid = dwarf_type.base_type.uuid
            return self.uc_get_new_base_expr(dwarf_type.uuid, pointed_type_uuid, arg.name)
        # TODO(boyan): support passing big (> 64 bits) parameters by value
        else:
            assert dwarf_type.is_basic
            assert dwarf_type.common.size <= 8
            return self.uc_get_new_data_expr(64, arg.name)  # Arguments always passed on 64 bits

    def uc_get_vtable_addr_for_class(self, class_name: str) -> int:
        """Return the virtual address of the vtable for 'class_name'."""
        with _UCSE_session.no_autoflush:
            vtables = _UCSE_session.query(_UCSE_graph.VTable).filter_by(class_name=class_name).all()
            if len(vtables) == 0:
                raise VTableException(f"No VTable found for class '{class_name}'")
            elif len(vtables) > 1:
                raise VTableException(f"Multiple VTables found for class '{class_name}'")
        return vtables[0].va

    def uc_get_all_dwarf_type_members(
        self, dwarf_type: DWARFType, additional_offset=0
    ) -> Tuple[int, List[Any]]:
        """Returns all the members of 'dwarf_type', including members inherited from parent classes.

        :param dwarf_type: The type for which to get all members. It MUST be
        a structure or a class
        :param additional_offset: Additional offset to add to offsets of 'dwarf_type' members.
        This is used to get the correct member layout for classes that inherit from multiple parent
        classes
        :return: A list of tuples (additional_offset, member_type) that contains all the
        member fileds for 'dwarf_type' in the correct order. For each tuple, 'additional_offset'
        must be added to 'member_type.common.offset' to get the real offset of the field in
        a class instance memory layout
        """
        res = []
        tmp_offset = additional_offset
        # Get parent members
        for parent in dwarf_type.parents:
            tmp_offset, members = self.uc_get_all_dwarf_type_members(parent, tmp_offset)
            res += members
        # Add own members
        dwarf_type = dwarf_get_base_type(dwarf_type)
        res += list(
            zip(
                itertools.repeat(additional_offset),
                sorted(dwarf_type.members, key=lambda x: x.common.offset),
            )
        )
        # Add own size ONLY IF the type wasn't optimized out by Empty-Base-Optimization
        # The type was EBO'd if its size is 1 and neither it nor its parents have members
        if not (dwarf_type.common.size == 1 and not res):
            # Add own size to additional offset for next fields
            additional_offset += dwarf_type.common.size
        # Return
        return (additional_offset, res)

    def uc_dwarf_type_to_expr_list(
        self, dwarf_type: DWARFType, base_obj_name: str, obj_count: int = 1
    ) -> List[Expression]:
        """Translates a dwarf type to a list of symbolic expressions matching the type.

        If the type is a built-in type (int, char, ...), a single expression is created.
        If the type is a complex struct or class, the list of expressions matching the
        structure layout is returned.

        :param dwarf_type: The type of the object we need to fill
        :param base_obj_name: The name of the parent object to use as a prefix to name the new
         symbolic variables
        :param obj_count: Number of consecutive objects to create. This will always be 1
        except for dynamic arrays that are referenced by a raw pointer: (type*) ptr
        """

        def _list_len(expr_list):
            return sum([e.size // 8 for e in expr_list])

        # Resolve type to the base type (real type definition)
        dwarf_type = dwarf_get_base_type(dwarf_type)
        res: List[Expression] = []

        for num in range(obj_count):
            # Add index to name if array
            # Remove "->" if obj_count > 1
            if obj_count > 1 and base_obj_name.endswith("->"):
                base_obj_name = base_obj_name[:-2]
            obj_name = base_obj_name if obj_count == 1 else f"{base_obj_name}[{num}]"

            #  Structure
            if dwarf_type.is_structure or dwarf_type.is_class:
                # If obj is not a pointer to a struct, add "." to the
                # field names
                if not obj_name.endswith("->"):
                    obj_name += "."

                # Convert all fields
                field_data: List[Expression] = []
                _, all_members = self.uc_get_all_dwarf_type_members(dwarf_type)
                for additional_offset, field in all_members:
                    field_name = obj_name + field.name
                    real_field_offset = field.common.offset + additional_offset
                    if field.name.startswith("_vptr$"):
                        # HACK: LLVM DWARF emission has a bug and doesn't export the correct vtable
                        # pointer information for child classes. To address this, we manually tweak
                        # the parent vptr field to replace it with the vptr for the correct class
                        if real_field_offset == 0:
                            vptr_class_name = dwarf_type.name
                        else:
                            vptr_class_name = field.name[6:]

                        # HACK2: We add 16 to the vtable address to get the value of the _vptr field
                        # because the vtable layout is <0, type_info_ptr, <virtual functions list>>
                        tmp_data = [
                            BitVecConstant(
                                size=self.memory_bit_size,
                                value=self.uc_get_vtable_addr_for_class(vptr_class_name) + 16,
                            )
                        ]
                    else:
                        tmp_data = self.uc_dwarf_type_to_expr_list(field, field_name)
                    assert _list_len(field_data) <= real_field_offset
                    if _list_len(field_data) < real_field_offset:
                        # Padding zeros
                        padding_len = real_field_offset - _list_len(field_data)
                        field_data.append(BitVecConstant(size=padding_len * 8, value=0))
                    field_data += tmp_data
                # Add zero padding in the end if needed
                if _list_len(field_data) < dwarf_type.common.size:
                    field_data.append(
                        BitVecConstant(
                            size=(dwarf_type.common.size - _list_len(field_data)) * 8, value=0
                        )
                    )
                res += field_data

            # basic types
            elif dwarf_type.is_basic:
                # For pointers to single variables, we still use the [0] syntax instead
                # of the '*' dereferencing operator
                tmp_name = f"{obj_name[:-2]}[0]" if obj_name.endswith("->") else obj_name
                res.append(self.uc_get_new_data_expr(dwarf_type.common.size * 8, tmp_name))

            #  array
            elif dwarf_type.is_array:
                count = dwarf_type.subrange.count
                elem_type = dwarf_type.base_type.common.name
                if elem_type not in ["int", "char"]:  # TODO, add other types?
                    raise Exception(f"Not implemented for array of {elem_type}")
                elem_size = dwarf_type.base_type.common.size * 8
                assert elem_size <= 64
                for i in range(count):
                    elem_name = f"{obj_name}[{i}]"
                    res.append(self.uc_get_new_data_expr(elem_size, elem_name))

            # pointer
            elif dwarf_is_pointer_or_reference_type(dwarf_type):
                pointed_type_uuid = dwarf_type.base_type.uuid
                res.append(self.uc_get_new_base_expr(dwarf_type.uuid, pointed_type_uuid, obj_name))

            # enum
            elif dwarf_type.is_enum:
                res += self.uc_dwarf_type_to_expr_list(dwarf_type.base_type, obj_name)

            else:
                raise Exception(f"Not implemented for type: {dwarf_type} : {dwarf_type.attributes}")

        return res

    def uc_base_has_object(self, base: str) -> bool:
        """Return True iff a MemObject was already allocated for this base."""
        return base in self.base_to_object

    def uc_get_object_for_base(self, base: str) -> MemObject:
        """
        Return the MemObject referenced by this base
        :return: MemObject if successful, None on failure
        """
        return self.base_to_object[base]

    def uc_fork_on_metavar(self, base: str, metavar: Metavar) -> None:
        """Fork on possible values for an object meta variables."""

        if base not in self.base_to_metavar_values[metavar]:
            # Fork on each possible value
            possible_values = list(self.uc_get_possible_metavar_values(base, metavar))

            def setstate(state, value):
                state.cpu.memory.base_to_metavar_values[metavar][base] = value

            raise Concretize(
                f"Forking on possible ${metavar.value} for base {base}",
                expression=self.base_to_metavars[base][metavar],
                setstate=setstate,
                policy="EXPLICIT",
                values=possible_values,
            )

    def _uc_get_metavar_solutions_for_current_state(
        self,
        metavar_bitvec: Expression,
        maxcnt: int,
    ) -> List[Expression]:
        """Generic internal method to get possible values for metavariables in the current state. If
        no possible value is found, raises an exception.

        :param metavar_bitvec: the expression to get possible values for
        :param maxcnt: maximum number of solutions to compute
        :return: set of possible values
        """
        all_values = SelectedSolver.instance().get_all_values(
            self.constraints.related_to(metavar_bitvec),
            metavar_bitvec,
            maxcnt=maxcnt,
            silent=True,
        )
        if not all_values:
            raise UncomputableMetaVar(
                f"No possible metavar value for expression {pretty_print(metavar_bitvec)}"
            )
        else:
            return all_values

    def uc_get_possible_metavar_values(
        self, base: str, metavar: Metavar, maxcnt: int = 5
    ) -> Set[int]:
        """Return the possible values for meta-variables in the current state. This method should
        not be used for the $LEN variable. See uc_get_possible_object_lengths() instead.

        :param base: base of the object
        :param metavar: which metavar of `base` object to get values for
        :param maxcnt: maximum count of possible values to return
        :return: set of possible values
        """
        metavar_bitvec = self.base_to_metavars[base][metavar]
        max_values = maxcnt + 1
        all_values = self._uc_get_metavar_solutions_for_current_state(metavar_bitvec, max_values)
        if len(all_values) < max_values:
            return set(all_values[:maxcnt])
        else:
            # When we get too many solutions, we consider that the metavar is not
            # constrained
            pass

        # Compute possible values from heuristics
        arbitrary_values_dict = {Metavar.CAPACITY: [1, 200], Metavar.SIZE: [0, 1, 10]}
        arbitrary_values = arbitrary_values_dict[metavar]
        # Check if arbitrary sizes are allowed by the state constraints
        possible_values = [
            val
            for val in arbitrary_values
            if SelectedSolver.instance().can_be_true(
                self.constraints.related_to(metavar_bitvec), metavar_bitvec == val
            )
        ]

        if possible_values:
            return set(possible_values[:maxcnt])
        else:
            return set(all_values[:maxcnt])

    def uc_get_possible_object_lengths(self, base: str, maxcnt=5) -> set:
        """Return the possible lengths for object 'base' considered as an array.

        :param base: base of the object to fill
        :param maxcnt: maximum count of possible lengths to return
        :return: set of possible sizes
        """
        # Get the type that points to the object
        # Note: Needed only for CPG strategy
        # ptr_dwarf_type = self.uc_get_dwarf_type_by_uuid(self.base_to_ptr_type[base])

        # Check with the solver whether the length is already constrained
        # by some constraints
        array_len_bitvec = self.base_to_metavars[base][Metavar.LEN]
        max_values = maxcnt + 1
        all_values = self._uc_get_metavar_solutions_for_current_state(array_len_bitvec, max_values)
        if len(all_values) < max_values:
            return set(all_values[:maxcnt])
        else:
            # When we get too many solutions, we consider that the metavar is not
            # constrained
            pass

        # TODO(boyan): handle the CPG unbounded pointer policy
        # At least find static strings or arrays when initialising a class...

        obj_type = dwarf_get_base_type(self.uc_get_dwarf_type_by_uuid(self.base_to_type[base]))
        # If CPG doesn't provide information, use heuristics for the size
        if obj_type.is_basic:
            if self.native_array_size_policy.policy_type == UnboundedPtrPolicyType.DEFAULT:
                arbitrary_values = [1, 256, 1000]
            elif self.native_array_size_policy.policy_type == UnboundedPtrPolicyType.CUSTOM:
                arbitrary_values = self.native_array_size_policy.custom_values
            else:
                raise Exception(
                    f"Unimplemented pointer policy {self.native_array_size_policy.policy_type}"
                )
        else:
            if self.complex_array_size_policy.policy_type == UnboundedPtrPolicyType.DEFAULT:
                arbitrary_values = [
                    1
                ]  # For now force complex type ptrs to point to single instances
            elif self.complex_array_size_policy.policy_type == UnboundedPtrPolicyType.CUSTOM:
                arbitrary_values = self.complex_array_size_policy.custom_values
            else:
                raise Exception(
                    f"Unimplemented pointer policy {self.complex_array_size_policy.policy_type}"
                )

        # Check if arbitrary sizes are allowed by the state constraints
        possible_values = [
            val
            for val in arbitrary_values
            if SelectedSolver.instance().can_be_true(
                self.constraints.related_to(array_len_bitvec), array_len_bitvec == val
            )
        ]

        if possible_values:
            return set(possible_values[:maxcnt])
        else:
            return set(all_values[:maxcnt])

    def uc_new_object_for_base(self, base: str) -> MemObject:
        """Effectively instanciate the object pointed to by the base."""
        with _UCSE_session.no_autoflush:
            logger.debug(f"Creating new object for base {base}")
            assert base in self.base_to_type
            assert not base in self.base_to_object
            obj_name = self.base_to_bitvec[base].name
            obj_content_type = self.uc_get_dwarf_type_by_uuid(self.base_to_type[base])
            obj_content_type_size = dwarf_get_base_type(obj_content_type).common.size

            obj = MemObject(int(base), obj_content_type_size, 0, obj_name, ConstraintSet())

            # Fork on possible meta variables if complex object
            if obj_content_type.is_class or obj_content_type.is_structure:
                for metavar in [Metavar.CAPACITY, Metavar.SIZE]:
                    # Necessary to pass linting checks
                    if self.user_constraints is None:
                        raise UCException("self.user_constraints shouldn't be None")

                    # We fork only if the meta variable is used in user constraints,
                    # otherwise its value is irrelevant (except for $LEN, on which
                    # we fork separately later in this method)
                    if self.user_constraints.variable_is_used(
                        self.uc_get_metavar_from_object_name(metavar, obj_name)
                    ):
                        self.uc_fork_on_metavar(base, metavar)

            # If the object was pointed to by a raw pointer, get the possible
            # array sizes
            if base not in self.base_to_metavar_values[Metavar.LEN]:
                # Fork on each possible array size
                possible_lengths = list(self.uc_get_possible_object_lengths(base))

                def setstate(state, value):
                    state.cpu.memory.base_to_metavar_values[Metavar.LEN][base] = value

                raise Concretize(
                    f"Forking on possible length for dynamic array {obj_name}",
                    expression=self.base_to_metavars[base][Metavar.LEN],
                    setstate=setstate,
                    policy="EXPLICIT",
                    values=possible_lengths,
                )

            # Init object symbolic contents
            obj.init(
                self.uc_dwarf_type_to_expr_list(
                    obj_content_type,
                    f"{obj_name}->",
                    obj_count=self.base_to_metavar_values[Metavar.LEN][base],
                )
            )

        self.base_to_object[base] = obj
        return obj


class UCLinux(SLinux):
    """Modifies the stock SLinux platform to use the custom memory model."""

    def _mk_proc(self, arch):
        mem = UCMemory64(None, None, self.constraints)
        return CpuFactory.get_cpu(mem, arch)
