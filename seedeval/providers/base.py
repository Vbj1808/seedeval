from __future__ import annotations

from abc import ABC, abstractmethod

from seedeval.models import GeneratedVideo


class SeedanceProvider(ABC):
    @abstractmethod
    async def generate_video(
        self,
        prompt: str,
        model: str,
        duration_s: int = 5,
    ) -> GeneratedVideo:
        """Generate a video and return its downloaded local path."""
