"""Shared pytest fixtures for database integration tests."""

import uuid

import psycopg
import pytest
from psycopg import sql

from database import database_connection_parameters


@pytest.fixture
def database_connection():
    """Connect to PostgreSQL and isolate a test inside its own temporary schema."""
    try:
        connection = psycopg.connect(
            **database_connection_parameters(),
            autocommit=True,
        )
    except (RuntimeError, psycopg.OperationalError) as error:
        pytest.fail(
            "PostgreSQL is required for this test. Start it with "
            f"'docker compose up -d --wait'. Details: {error}"
        )

    schema_name = f"pytest_{uuid.uuid4().hex}"
    with connection.cursor() as cursor:
        cursor.execute(
            sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema_name))
        )
        cursor.execute(
            sql.SQL("SET search_path TO {}").format(sql.Identifier(schema_name))
        )

    try:
        yield connection
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SET search_path TO public")
            cursor.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema_name))
            )
        connection.close()
