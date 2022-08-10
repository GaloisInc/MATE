import enum
import operator
import re
import string
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple

from lark import Lark
from lark import Token as LarkToken
from lark import Transformer as LarkTransformer
from lark import Tree as LarkTree
from lark import Visitor as LarkVisitor
from lark.exceptions import UnexpectedInput
from manticore.core.smtlib import BitVec, ConstraintSet, Expression, Operators, pretty_print

from mate_common.models.manticore import UserDefinedConstraint
from mate_query.cpg.models import DWARFType

from .dwarf_helper import dwarf_get_template_type_argument
from .exceptions import InputError, UCException
from .logging import logger
from .smt import SmtNameTranslator


@dataclass(frozen=False)
class ParsedConstraint:
    original_constraint: UserDefinedConstraint
    tree: Optional[LarkTree]


@dataclass(frozen=False)
class ParsedClassConstraint(ParsedConstraint):
    class_spec: str
    used_at_least_once: bool = False


@dataclass(frozen=False)
class ParsedPointsWithinConstraint(ParsedConstraint):
    points_within: Tuple[str, str]


class MakeVariablesSmtCompliant(LarkTransformer):
    """Transformer that transforms symbolic variable names to make them SMT compliant.

    It replaces characters not supported by smtlib such as "[", "]", ...
    """

    def _generic_var(self, token):
        token.value = SmtNameTranslator.make_name_smt_compliant(str(token))
        return token

    def VAR(self, token):
        return self._generic_var(token)

    def LEN_METAVAR(self, token):
        return self._generic_var(token)

    def CAPACITY_METAVAR(self, token):
        return self._generic_var(token)

    def SIZE_METAVAR(self, token):
        return self._generic_var(token)


def lark_make_variables_smt_compliant(parsed_constraint: LarkTree) -> LarkTree:
    """Make all VAR tokens SMT compliant in a parsed constraint."""
    return MakeVariablesSmtCompliant().transform(parsed_constraint)


class GetAllVariables(LarkVisitor):
    """Visitor that returns the names of all symbolic variables present in a parsed constraint
    tree."""

    def __init__(self):
        super().__init__()
        self.result: Set[str] = set()

    def atom(self, tree):
        for child in tree.children:
            if child.type == "VAR" or child.type.endswith("_METAVAR"):
                self.result.add(str(child.value))


def lark_get_all_variables(parsed_constraint: LarkTree) -> Set[str]:
    """Get all the names of symbolic variables present in a parsed constraint."""
    visitor = GetAllVariables()
    visitor.visit(parsed_constraint)
    return visitor.result


class TranslateConstraint(LarkTransformer):
    """Transformer that translates a parsed user constraint tree into an actual Expression object to
    be used by Manticore."""

    OPERATOR_MAP = {
        "op_add": operator.add,
        "op_sub": operator.sub,
        "op_mul": operator.mul,
        "op_and": operator.and_,
        "op_or": operator.or_,
        "op_xor": operator.xor,
        "op_shr": operator.rshift,
        "op_shl": operator.lshift,
        "op_mod": operator.mod,
        "op_neg": operator.neg,
        "op_inv": operator.inv,
        "op_concat": lambda x, y: Operators.CONCAT(x.size + y.size, x, y),
        "op_sdiv": lambda x, y: x.sdiv(y),
        "op_sar": lambda x, y: x.sar(y),
        "op_eq": operator.eq,
        "op_neq": operator.ne,
        "op_lt": operator.lt,
        "op_le": operator.le,
        "op_gt": operator.gt,
        "op_ge": operator.ge,
        "op_ult": lambda x, y: x.ult(y),
        "op_ule": lambda x, y: x.ule(y),
        "op_uge": lambda x, y: x.uge(y),
        "op_ugt": lambda x, y: x.ugt(y),
    }

    def __init__(self, constraints: ConstraintSet):
        self.constraints = constraints

    @staticmethod
    def _get_operator(op):
        operator = TranslateConstraint.OPERATOR_MAP.get(str(op.data), None)
        if operator is None:
            raise Exception(
                f"Missing implementation for operator '{op.data}' when translating user-defined constraint"
            )
        return operator

    def _generic_var(self, token):
        var_name = str(token.value)
        var = self.constraints.get_variable(var_name)
        if var is None:
            raise Exception(f"Unexpected error, variable {var_name} not present in contraint set!")
        return var

    def VAR(self, token: LarkToken):
        return self._generic_var(token)

    def LEN_METAVAR(self, token: LarkToken):
        return self._generic_var(token)

    def CAPACITY_METAVAR(self, token: LarkToken):
        return self._generic_var(token)

    def SIZE_METAVAR(self, token: LarkToken):
        return self._generic_var(token)

    def NUMBER(self, token: LarkToken):
        return int(token, 16 if token.startswith("0x") else 10)

    def atom(self, tokens: List[LarkToken]):
        return tokens[0]

    def expr(self, tokens: List[LarkToken]):
        assert len(tokens) == 1
        return tokens[0]

    def funclike_comparison(self, tokens: List[LarkToken]):
        op, left, right = tokens
        # Func-like comparisons are unsigned, so zero-extend if needed
        if isinstance(left, BitVec) and isinstance(right, BitVec):
            if left.size < right.size:
                left = Operators.ZEXTEND(left, right.size)
            elif left.size > right.size:
                right = Operators.ZEXTEND(right, left.size)
        operator = TranslateConstraint._get_operator(op)
        return operator(left, right)

    def binary_operation(self, tokens: List[LarkToken]):
        left, op, right = tokens
        operator = TranslateConstraint._get_operator(op)
        return operator(left, right)

    def funclike_operation(self, tokens: List[LarkToken]):
        op, left, right = tokens
        operator = TranslateConstraint._get_operator(op)
        return operator(left, right)

    def unary_operation(self, tokens: List[LarkToken]):
        op, arg = tokens
        operator = TranslateConstraint._get_operator(op)
        return operator(arg)

    def extract_operation(self, tokens: List[LarkToken]):
        arg, offset, size = tokens
        return Operators.EXTRACT(arg, offset, size)

    def constraint_disjunction(self, tokens: List[LarkToken]):
        left, right = tokens
        return left | right

    def regular_comparison(self, tokens: List[LarkToken]):
        left, cmp_op, right = tokens
        # Regular comparisons are signed, so sign-extend if needed
        if isinstance(left, BitVec) and isinstance(right, BitVec):
            if left.size < right.size:
                left = Operators.SEXTEND(left, left.size, right.size)
            elif left.size > right.size:
                right = Operators.SEXTEND(right, right.size, left.size)
        operator = TranslateConstraint._get_operator(cmp_op)
        return operator(left, right)

    def constraint(self, tokens: List[LarkToken]):
        return tokens[0]

    def points_within_constraint(self, tokens: List[LarkToken]):
        raise Exception(
            "$POINTS_WITHIN() constraint should not be translated as regular constraint!"
        )


def lark_translate_constraint(
    parsed_constraint: LarkTree, constraints: ConstraintSet
) -> Expression:
    """Translate a parsed user constraint tree into an actual Expression object to be used by
    Manticore."""
    transformer = TranslateConstraint(constraints)
    return transformer.transform(parsed_constraint)


class TranslatePointsWithinConstraint(LarkTransformer):
    """Transformer that translates a parsed $POINTS_WITHIN constraint tree into an tuple
    (ptr_pointing_within_ptr2, ptr2)"""

    def VAR(self, token: LarkToken):
        var_name = str(token.value)
        return var_name  # Return the name only

    def points_within_constraint(self, tokens: List[LarkToken]):
        return (
            tokens[0],
            tokens[1],
        )


class SplitGenericClassConstraint(LarkTransformer):
    """Transformer that splits a generic class constraint into the class specifier string and the
    actual parsed constraint."""

    def generic_class_constraint(self, tokens: List[LarkToken]):
        return (
            tokens[0],
            tokens[1],
        )

    def CLASS_SPEC(self, token: LarkToken):
        return str(token.value)


def lark_translate_points_within_constraint(parsed_constraint: LarkTree) -> Expression:
    """Translate a parsed $POINTS_WITHIN constraint into an tuple (ptr_pointing_within_ptr2,
    ptr2)"""
    transformer = TranslatePointsWithinConstraint()
    return transformer.transform(parsed_constraint)


def lark_split_generic_class_constraint(parsed_constraint: LarkTree) -> Tuple[str, LarkTree]:
    """Split a generic class constraint into the class specifier string and the actual parsed
    constraint."""
    transformer = SplitGenericClassConstraint()
    return transformer.transform(parsed_constraint)


class ReplacePatternInVariables(LarkTransformer):
    """Transformer replaces a string by another in all variable names."""

    def __init__(self, old: str, new: str):
        self.old = old
        self.new = new

    def VAR(self, token: LarkToken):
        token.value = token.value.replace(self.old, self.new)
        return token

    def CAPACITY_METAVAR(self, token: LarkToken):
        token.value = token.value.replace(self.old, self.new)
        return token

    def SIZE_METAVAR(self, token: LarkToken):
        token.value = token.value.replace(self.old, self.new)
        return token

    def LEN_METAVAR(self, token: LarkToken):
        token.value = token.value.replace(self.old, self.new)
        return token


def lark_replace_pattern_in_variables(parsed_constraint: LarkTree, old: str, new: str) -> LarkTree:
    """Replace a given string in all variables in a parsed constraint.

    :param old: string to replace
    :param new: string to substitute to 'old'
    """
    transformer = ReplacePatternInVariables(old, new)
    return transformer.transform(parsed_constraint)


class InstanciateClassConstraintForType(LarkTransformer):
    """See lark_instanciate_class_constraint_for_type() for documentation."""

    def __init__(self, obj_type: DWARFType):
        self.obj_type: DWARFType = obj_type

    def typesize(self, tokens: List[LarkToken]):
        template_num = int(tokens[0].split(UserConstraintManager._TEMPLATE_TYPE_SPEC)[1])
        template_type = dwarf_get_template_type_argument(self.obj_type, template_num)
        type_size = template_type.common.size
        # Replace typesize operation by the actual value in a NUMBER token
        return LarkToken("NUMBER", str(type_size))


def lark_instanciate_class_constraint_for_type(
    parsed_constraint: LarkTree, obj_type: DWARFType
) -> LarkTree:
    """Instanciate a generic class constraint for a given type. This method will replace special
    variables and special operators that are specific to generic class constraints, such as getting
    the size of template type arguments, etc.

    :param parsed_constraint: the intermediate parsed constraint to instanciate for the given type
    :param obj_type: type for which to instanciate the class constraint. In most cases,
    'obj_type' will simply be the type specified by the generic constraint class specifier.
    But when dealing with templated types the same generic constraint can be instanciated
    for different combinations of template type arguments
    """
    transformer = InstanciateClassConstraintForType(obj_type)
    return transformer.transform(parsed_constraint)


class Metavar(enum.Enum):
    """Types of meta variables for objects."""

    LEN = "LEN"
    CAPACITY = "CAPACITY"
    SIZE = "SIZE"


class UserConstraintManager:
    """Class that manages constraints supplied by the user.

    Its intended usage is roughly:
    - Use add() to add user-defined constraints (which are just strings)
    - Use apply_constraints(<var>) to apply any pending parsed constraints that involves variable
      <var>. The parsed constraint tree is then translated into a Manticore Expression object
      and added to the Manticore state

    Example constraints:
        a < 10000
        ULE(a, b+1)
        arg1->x == arg2.y
        arg.array[5] > 6
        $LEN(arg.array) < 100
        a == 1 || b == 5
        Extract(d, 16, 32)
    """

    _OBJ_VAR: str = "$OBJ"  # Special var that refers to a class instance for generic constraints
    _TEMPLATE_TYPE_SPEC: str = "#"  # Special char for specifying template type in a class spec
    _LEN_OP = f"${Metavar.LEN.value}"
    _CAPACITY_OP = f"${Metavar.CAPACITY.value}"
    _SIZE_OP = f"${Metavar.SIZE.value}"

    CONSTRAINT_GRAMMAR = rf"""
            %import common.WS
            %ignore WS

            constraint: regular_comparison
                | funclike_comparison
                | "(" constraint ")"
                | constraint_disjunction

            constraint_disjunction: constraint "||" constraint

            funclike_cmp_op: "ULE" -> op_ule
                | "ULT" -> op_ult
                | "UGT" -> op_ugt
                | "UGE" -> op_uge

            funclike_comparison: funclike_cmp_op "(" expr "," expr ")"
            regular_comparison: expr cmp_op expr

            expr: atom
                | binary_operation
                | unary_operation
                | funclike_operation
                | extract_operation
                | "(" expr ")"
                | special_operation

            special_operation: "$TYPESIZE(" TEMPLATE_VAR ")" -> typesize

            funclike_op: "CONCAT" -> op_concat
                | "SDIV" -> op_sdiv
                | "SAR" -> op_sar

            funclike_operation: funclike_op "(" expr "," expr ")"

            extract_operation: "EXTRACT" "(" expr "," NUMBER "," NUMBER ")"

            binary_operation: expr binop expr

            unary_operation: unop expr

            atom: VAR | NUMBER | LEN_METAVAR | CAPACITY_METAVAR | SIZE_METAVAR

            cmp_op: "==" -> op_eq
                | "!=" -> op_neq
                | "<" -> op_lt
                | "<=" -> op_le
                | ">" -> op_gt
                | ">=" -> op_ge

            binop: "+" -> op_add
                | "-" -> op_sub
                | "*" -> op_mul
                | "&" -> op_and
                | "|" -> op_or
                | "^" -> op_xor
                | ">>" -> op_shr
                | "<<" -> op_shl
                | "%" -> op_mod

            unop: "-" -> op_neg
                | "~" -> op_inv


            %import common.LETTER
            %import common.DIGIT
            // We add $OBJ. for variables in generic class constraints
            VAR: (("{_OBJ_VAR}.")? ("_"|LETTER) ("_"|"."|"->"|LETTER|DIGIT|IDX)*)
                | "{_OBJ_VAR}"

            LEN_METAVAR: "{_LEN_OP}(" VAR ")"
            CAPACITY_METAVAR: "{_CAPACITY_OP}(" VAR ")"
            SIZE_METAVAR: "{_SIZE_OP}(" VAR ")"

            TEMPLATE_VAR: "{_TEMPLATE_TYPE_SPEC}" (DIGIT)+

            IDX: "[" (DIGIT)+ "]"

            %import common.SIGNED_INT
            %import common.HEXDIGIT
            NUMBER: SIGNED_INT | ("0x" (HEXDIGIT)+)

            points_within_constraint: "$POINTS_WITHIN(" VAR "," VAR ")"

            generic_class_constraint: CLASS_SPEC ":" (constraint|points_within_constraint)

            CLASS_SPEC: ("_"|LETTER) (CLASS_SPEC_CHAR)*
            CLASS_SPEC_CHAR: "::"|","|"_"|"<"|">"|"{_TEMPLATE_TYPE_SPEC}"|LETTER|DIGIT|WS
            """

    def __init__(self):
        self.constraint_parser = Lark(
            UserConstraintManager.CONSTRAINT_GRAMMAR,
            start=["constraint", "points_within_constraint", "generic_class_constraint"],
        )
        # Regular pending constraints to be added to the symbolic state
        self.parsed_constraints: List[ParsedConstraint] = []
        # Points-within constraints (as tuples: x[1] points within x[2])
        self.points_within_constraints: List[ParsedPointsWithinConstraint] = []
        # Generic class constraints as tuples (class_spec, parsed_constraint)
        self.generic_class_constraints: List[ParsedClassConstraint] = []

    def is_points_within_constraint(self, parsed):
        return parsed.data == "points_within_constraint"

    def is_generic_class_constraint(self, parsed):
        return parsed.data == "generic_class_constraint"

    @classmethod
    def _remove_whitespaces_in_string(
        cls, constraint: UserDefinedConstraint
    ) -> UserDefinedConstraint:
        return constraint.replace(" ", "").replace("\t", "")

    def add(self, constraint: UserDefinedConstraint):
        """Add and parse a user-defined constraint.

        - The user is parsed according to the constraint grammar and stored as a
          'parsed constraint tree' which is an intermediate representation on which
          we can easily run visitors
        - The symbolic variable names in the constraint that aren't smtlibv2-compliant
          are transformed (unique predefined strings replace non-compliant characters)
        - The parsed constraint is added to an internal list of pending constraints
          that will later be applied to a Manticore state

        If a constraint is invalid and can not be parsed, this method raises an
        'InputError' exception

        :param constraint: The user constraint to add and parse
        :return: None
        """
        parsed: Optional[LarkTree] = None
        debug_msgs = []
        orig_constraint = constraint

        for constraint_type in [
            "constraint",
            "points_within_constraint",
            "generic_class_constraint",
        ]:
            try:
                parsed = self.constraint_parser.parse(str(constraint), start=constraint_type)
                break
            except UnexpectedInput as e:
                debug_msgs.append(f"User-constraint parsing error: {e}")
                pass
        if parsed is None:
            for msg in debug_msgs:
                logger.debug(msg)
            raise InputError(f"Invalid user-defined constraint: '{str(constraint)}'")

        # Separate class spec from constraint if generic constraint
        if self.is_generic_class_constraint(parsed):
            class_spec, constraint = lark_split_generic_class_constraint(parsed)
        else:
            class_spec, constraint = (None, parsed)

        # Apply a transformer to transform the special operators
        # and the brackets to have SMT compliant variable names. This needs to
        # be through the same util class used by UCMemory to create UC objects
        constraint = lark_make_variables_smt_compliant(constraint)

        if class_spec:
            self.generic_class_constraints.append(
                ParsedClassConstraint(orig_constraint, constraint, class_spec)
            )
        else:
            self._add_parsed_constraint(ParsedConstraint(orig_constraint, constraint))

    def _add_parsed_constraint(self, parsed_constraint: ParsedConstraint):
        """Util method that adds a parsed constraint in the correct internal list depending on the
        type of constraint, and does necessary additional processing."""
        constraint = parsed_constraint.tree
        # Add parsed constraint to list
        if self.is_points_within_constraint(constraint):
            var1, var2 = lark_translate_points_within_constraint(constraint)
            # Sanity checks
            if var1 == var2:
                raise InputError(
                    f"In {constraint}: cannot use the same variable as source and destination"
                )
            if any(x.points_within[0] == var2 for x in self.points_within_constraints):
                raise InputError(
                    f"In {constraint}: variable '{var2}' cannot be used both as source and destination in different $POINTS_WITHIN() constraint"
                )
            if any(x.points_within[1] == var1 for x in self.points_within_constraints):
                raise InputError(
                    f"In {constraint}: variable '{var1}' cannot be used both as source and destination in different $POINTS_WITHIN() constraint"
                )
            self.points_within_constraints.append(
                ParsedPointsWithinConstraint(
                    parsed_constraint.original_constraint, constraint, (var1, var2)
                )
            )
        else:
            self.parsed_constraints.append(parsed_constraint)

    def apply_class_constraints(self, obj_name: str, obj_type: DWARFType):
        """Apply generic class constraints to an object, if applicable. This generates new
        constraints specific to that object, to be apply later by a call to apply_constraints()

        :param obj_name: The object name. It must include the field accessor operator or
        the dereference operator ('a.') or ('a->')
        :param obj_type: The DWARFType of the object
        """
        for p in self.generic_class_constraints:
            if UserConstraintManager._dwarf_type_matches_class_spec(obj_type, p.class_spec):
                p.used_at_least_once = True
                self._apply_class_constraint(obj_name, obj_type, p)

    def _apply_class_constraint(
        self, obj_name: str, obj_type: DWARFType, constraint: ParsedClassConstraint
    ):
        parsed_constraint = constraint.tree
        # Replace $OBJ. with object name
        new_constraint = lark_replace_pattern_in_variables(
            parsed_constraint, f"{UserConstraintManager._OBJ_VAR}.", obj_name
        )
        # Also replace single $OBJ occurences (without following '.' field accessor)
        if obj_name.endswith("->"):
            bare_name = obj_name[:-2]
        elif obj_name.endswith("."):
            bare_name = obj_name[:-1]
        else:
            bare_name = obj_name
        new_constraint = lark_replace_pattern_in_variables(
            new_constraint, f"{UserConstraintManager._OBJ_VAR}", bare_name
        )

        # Replace special variables and resolve special operators
        # Note(boyan): this is done here only because instanciating special
        # variables and operators for non-class constraints doesn't make sense
        new_constraint = lark_instanciate_class_constraint_for_type(new_constraint, obj_type)

        # Add new intermediate constraint tree to constraints list
        self._add_parsed_constraint(
            ParsedConstraint(constraint.original_constraint, new_constraint)
        )

    def apply_constraints(self, constraints: ConstraintSet, var: str):
        """Apply pending user defined constraints related to a given expression to a constraint set.

        - A parsed constraint is applied only if all the variables it contains are already
          defined in the 'constraints' constraint set (not only 'var')
        - A parsed constraint being applied is translated into a Manticore Expression
          and then added to the constraint set
        - Parsed constraints that are applied are removed from the list of pending
          parsed constraints

        :param constraints: The constraint set to which to add user defined constraints
        :param var: The name of the variable to which user constraints must be related in order to
        be added to the constraint set
        :return None:
        """

        remaining_constraints = []
        for p in self.parsed_constraints:
            user_constraint = p.tree
            constraint_vars = lark_get_all_variables(user_constraint)

            # Skip constraints not related to 'var'
            if var not in constraint_vars:
                remaining_constraints.append(p)
                continue

            # Make sure that all the user constraint variables are present
            # in the constraint set. If not, we keep the constraint for later
            # when all variables will be introduced
            if any([var for var in constraint_vars if constraints.get_variable(var) is None]):
                remaining_constraints.append(p)
                continue

            # Translate into manticore constraint
            constraint = lark_translate_constraint(user_constraint, constraints)
            constraints.add(constraint)
            logger.debug(f"Applied symbolic constraint: {pretty_print(constraint)}")

        # Update the constraint list with only the remaining constraints
        self.parsed_constraints = remaining_constraints

    def points_within_other_variable(self, var_name: str) -> bool:
        return any(x.points_within[0] == var_name for x in self.points_within_constraints)

    def get_points_within_destination(self, var_name: str) -> str:
        try:
            # Note: is there a more pythonic way to do this?
            constraint = next(
                c for c in self.points_within_constraints if c.points_within[0] == var_name
            )
            self.points_within_constraints.remove(constraint)
            return constraint.points_within[1]
        except StopIteration:
            raise UCException(f"No $POINTS_WITHIN constraint for {var_name}")

    @classmethod
    def _dwarf_type_matches_class_spec(cls, dwarf_type, class_spec: str) -> bool:
        """Return true if 'class_spec' can refer to the type 'dwarf_type'."""
        type_name = UserConstraintManager._remove_whitespaces_in_string(dwarf_type.common.name)
        for whitespace in string.whitespace:
            class_spec = class_spec.replace(whitespace, "")
        pattern = class_spec.replace(cls._TEMPLATE_TYPE_SPEC, "(.*)")
        matcher = re.compile(pattern)
        match = matcher.match(type_name)
        # Make sure that we matched the whole class name, e.g:
        # prevent 'my_class<a,b>' to match 'my_class<a,b>::c'
        res = (not match is None) and (match.span()[1] == len(type_name))
        return res

    def variable_is_used(self, variable_name: str) -> bool:
        """Return true if 'variable_name' is used in at least one instanciated user constraint.

        This ignores generic class constraints that haven't been instanciated
        """
        return any(
            [c for c in self.parsed_constraints if variable_name in lark_get_all_variables(c.tree)]
        )

    def get_unused_constraints(self) -> List[str]:
        """Return the list of user constraints that were not used during execution."""
        res: List[str] = [p.original_constraint for p in self.parsed_constraints]
        res += [
            p.original_constraint
            for p in self.generic_class_constraints
            if not p.used_at_least_once
        ]
        res += [p.original_constraint for p in self.points_within_constraints]
        return res
