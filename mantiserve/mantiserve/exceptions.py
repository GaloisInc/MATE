from typing import Any, Optional


class MantiserveError(Exception):
    def __init__(self, *args: Any, logs: Optional[bytes] = None) -> None:
        super().__init__(*args)
        self.logs = logs
