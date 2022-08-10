from typing import Any, List


def info(obj_list: List[Any]) -> None:
    """Shorthand to display useful information given a list of Nodes or Edges."""
    for x in obj_list:
        print(x, x.attributes)
