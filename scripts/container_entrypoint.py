from __future__ import annotations

import os
import sys


def main() -> None:
    raw_port = os.environ.get("PORT", "8000")
    try:
        port = int(raw_port)
    except ValueError as error:
        raise SystemExit(f"PORT must be an integer, received {raw_port!r}") from error
    if not 1 <= port <= 65_535:
        raise SystemExit("PORT must be between 1 and 65535")

    os.execv(
        sys.executable,
        [
            sys.executable,
            "-m",
            "uvicorn",
            "queryweaver.api:app",
            "--host",
            "0.0.0.0",
            "--port",
            str(port),
            "--proxy-headers",
        ],
    )


if __name__ == "__main__":
    main()
