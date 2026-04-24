from __future__ import annotations

import asyncio
import json

from seedeval.agents.vlm_judge import judge_frame
from seedeval.checks.adherence import _build_adherence_prompt

FRAME_PATH = "artifacts/01KPYEWQ9ZNWSE0CHKM53SJ5BS/frames/000.jpg"
PROMPT = (
    "A bustling Times Square at night with neon signs, yellow taxis, and crowds of "
    "people, shot on IMAX with cinematic depth of field"
)


async def main() -> None:
    result = await judge_frame(
        FRAME_PATH,
        PROMPT,
        _build_adherence_prompt(PROMPT, 0, 0.0),
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
