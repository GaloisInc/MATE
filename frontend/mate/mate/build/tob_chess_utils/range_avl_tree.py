from __future__ import annotations

from typing import List, Optional

"""
Based off of https://rosettacode.org/wiki/AVL_tree#Python and adapted to work for nodes with a range key value.
"""


class RangeAVLNode(object):
    """A node in the RangeAVL tree."""

    height: int = -1

    def __init__(
        self, parent: Optional[RangeAVLNode], lower: int, upper: int, label: Optional[str]
    ) -> None:
        self.lower = lower
        self.upper = upper
        self.parent = parent
        self.label = label if label else str(range(lower, upper))
        self.left: Optional[RangeAVLNode] = None
        self.right: Optional[RangeAVLNode] = None

    def find(self, val: int) -> Optional[RangeAVLNode]:
        """Given a value val, return the label associated with the range in which it fits.

        If no range exists that contains val, return None
        """

        if val < self.lower:
            if self.left is not None:
                return self.left.find(val)
            else:
                return None
        # Upper is not inclusive, so go to next node
        elif val >= self.upper:
            if self.right is not None:
                return self.right.find(val)
            else:
                return None
        else:
            return self

    def find_min(self) -> Optional[RangeAVLNode]:
        current = self
        while current.left is not None:
            current = current.left
        return current

    def next_larger(self) -> Optional[RangeAVLNode]:
        if self.right is not None:
            return self.right.find_min()
        current = self
        while current.parent is not None and current is current.parent.right:
            current = current.parent
        return current.parent

    def insert(self, node: RangeAVLNode) -> None:
        """Insertion node cannot overlap ranges of existing RangeAVLNodes."""
        if node.upper <= self.lower:
            if self.left is None:
                node.parent = self
                self.left = node
            else:
                self.left.insert(node)
        elif node.lower >= self.upper:
            if self.right is None:
                node.parent = self
                self.right = node
            else:
                self.right.insert(node)
        else:
            errmsg = "Improper bounds on insertion node: "
            self_range = range(self.lower, self.upper)
            if node.lower in self_range:
                errmsg += f"node.lower ({node.lower}) is in {self_range}"
            elif node.upper in self_range:
                errmsg += f"node.upper ({node.upper}) is in {self_range}"
            else:
                errmsg += f"Unknown range error: node={range(node.lower, node.upper)} and self={self_range}"
            raise ValueError(errmsg)


def height(node: Optional[RangeAVLNode]) -> int:
    if node is None:
        return -1
    else:
        return node.height


def update_height(node: RangeAVLNode) -> None:
    node.height = max(height(node.left), height(node.right)) + 1


class RangeAVL(object):
    """AVL binary search tree that uses non-overlapping integer ranges in Nodes."""

    def __init__(self) -> None:
        """empty tree."""
        self.root: Optional[RangeAVLNode] = None

    def find(self, val: int) -> Optional[RangeAVLNode]:
        """Returns the label associated with the range that val falls in, or None."""
        return self.root and self.root.find(val)

    def find_min(self) -> Optional[RangeAVLNode]:
        return self.root and self.root.find_min()

    def next_larger(self, k: int) -> Optional[RangeAVLNode]:
        node = self.find(k)
        return node and node.next_larger()

    def left_rotate(self, x: RangeAVLNode) -> None:
        y = x.right
        assert y is not None
        y.parent = x.parent
        if y.parent is None:
            self.root = y
        else:
            if y.parent.left is x:
                y.parent.left = y
            elif y.parent.right is x:
                y.parent.right = y
        x.right = y.left
        if x.right is not None:
            x.right.parent = x
        y.left = x
        x.parent = y
        update_height(x)
        update_height(y)

    def right_rotate(self, x: RangeAVLNode) -> None:
        y = x.left
        assert y is not None
        y.parent = x.parent
        if y.parent is None:
            self.root = y
        else:
            if y.parent.left is x:
                y.parent.left = y
            elif y.parent.right is x:
                y.parent.right = y
        x.left = y.right
        if x.left is not None:
            x.left.parent = x
        y.right = x
        x.parent = y
        update_height(x)
        update_height(y)

    def rebalance(self, node: Optional[RangeAVLNode]) -> None:
        while node is not None:
            update_height(node)
            if height(node.left) >= 2 + height(node.right):
                assert node.left is not None
                if height(node.left.left) >= height(node.left.right):
                    self.right_rotate(node)
                else:
                    self.left_rotate(node.left)
                    self.right_rotate(node)
            elif height(node.right) >= 2 + height(node.left):
                assert node.right is not None
                if height(node.right.right) >= height(node.right.left):
                    self.left_rotate(node)
                else:
                    assert node.right is not None
                    self.right_rotate(node.right)
                    self.left_rotate(node)
            node = node.parent

    def insert(self, range_lower: int, range_upper: int, label: Optional[str]) -> None:
        """Inserts a node with key k into the subtree rooted at this node.
        This AVL version guarantees the balance property: h = O(lg n).

        Args:
            range_lower: The lower bound of the node to be inserted.
            range_upper: The upper bound (exclusive) of the node to be inserted.
            label: A label to assign the range, otherwise f"range({range_lower}, {range_upper})"
        """
        if label is None:
            label = str(range(range_lower, range_upper))
        node = RangeAVLNode(None, range_lower, range_upper, label)
        if self.root is None:
            # The root's parent is None.
            self.root = node
        else:
            self.root.insert(node)
        self.rebalance(node)


def inorder(node: Optional[RangeAVLNode]) -> List[RangeAVLNode]:
    lst = []

    def _inorder(_node: Optional[RangeAVLNode]) -> None:
        if _node is not None:
            inorder(_node.left)
            lst.append(_node)
            inorder(_node.right)

    _inorder(node)
    return lst
