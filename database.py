"""Shared PostgreSQL connection configuration."""

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_DIR = Path(__file__).resolve().parent
DATABASE_ENVIRONMENT_VARIABLES = (
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
)


def database_connection_parameters() -> dict[str, str | int]:
    """Return psycopg connection parameters from the environment."""
    load_dotenv(PROJECT_DIR / ".env")

    missing = [name for name in DATABASE_ENVIRONMENT_VARIABLES if not os.environ.get(name)]
    if missing:
        names = ", ".join(missing)
        raise RuntimeError(f"Missing required database environment variables: {names}")

    port_value = os.environ["POSTGRES_PORT"]
    try:
        port = int(port_value)
    except ValueError as error:
        raise RuntimeError("POSTGRES_PORT must be an integer") from error

    if not 1 <= port <= 65535:
        raise RuntimeError("POSTGRES_PORT must be between 1 and 65535")

    return {
        "dbname": os.environ["POSTGRES_DB"],
        "user": os.environ["POSTGRES_USER"],
        "password": os.environ["POSTGRES_PASSWORD"],
        "host": os.environ["POSTGRES_HOST"],
        "port": port,
    }
