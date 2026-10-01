import sys

import uvicorn
from pydantic import ValidationError

from app.core.config import Settings
from app.main import create_app


def main() -> None:
    try:
        settings = Settings()
        application = create_app(settings)
    except (ValidationError, ValueError):
        # Do not print raw configuration exceptions: their context can contain secret inputs.
        print(
            "Invalid CareerPilot configuration. Check environment variable names and policy.",
            file=sys.stderr,
        )
        raise SystemExit(2) from None
    uvicorn.run(
        application,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        access_log=False,
    )


if __name__ == "__main__":
    main()
