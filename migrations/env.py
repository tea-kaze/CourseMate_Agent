from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from coursemate.config import get_settings, normalize_database_url
from coursemate.db.models import Base


config = context.config
configured_url = config.get_main_option("sqlalchemy.url")
database_url = normalize_database_url(
    configured_url or get_settings().DATABASE_URL
)
config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _configured_version_schema() -> str | None:
    value = config.get_main_option("version_table_schema")
    return (value.strip() or None) if value else None


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        version_table_schema=_configured_version_schema(),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.begin() as connection:
        version_schema = _configured_version_schema()
        if version_schema is None:
            version_schema = connection.exec_driver_sql(
                "SELECT current_schema()"
            ).scalar_one()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            version_table_schema=version_schema,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
