from __future__ import annotations

import sqlite3
from abc import ABC, abstractmethod

from seedeval.models import CheckResult


class Check(ABC):
    name: str

    @abstractmethod
    async def run(self, run_id: str, conn: sqlite3.Connection) -> CheckResult:
        """Execute the check, write to check_results, and return the result."""
