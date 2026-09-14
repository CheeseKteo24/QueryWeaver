from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ColumnSchema:
    name: str
    data_type: str
    nullable: bool
    primary_key: bool


@dataclass(frozen=True, slots=True)
class TableSchema:
    name: str
    columns: tuple[ColumnSchema, ...]


@dataclass(frozen=True, slots=True)
class SchemaCatalog:
    tables: tuple[TableSchema, ...]

    @classmethod
    def from_sqlite(
        cls, connection: sqlite3.Connection, *, include_tables: frozenset[str] | None = None
    ) -> SchemaCatalog:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        ).fetchall()
        requested = {name.casefold() for name in include_tables} if include_tables else None
        tables: list[TableSchema] = []
        for (raw_name,) in rows:
            table_name = str(raw_name)
            if table_name.casefold().startswith("sqlite_"):
                continue
            if requested is not None and table_name.casefold() not in requested:
                continue
            quoted_name = table_name.replace('"', '""')
            column_rows = connection.execute(f'PRAGMA table_info("{quoted_name}")').fetchall()
            columns = tuple(
                ColumnSchema(
                    name=str(column[1]),
                    data_type=str(column[2] or "UNKNOWN"),
                    nullable=not bool(column[3]),
                    primary_key=bool(column[5]),
                )
                for column in column_rows
            )
            tables.append(TableSchema(table_name, columns))
        return cls(tuple(tables))

    @property
    def table_names(self) -> frozenset[str]:
        return frozenset(table.name.casefold() for table in self.tables)

    def columns_for(self, table_name: str) -> frozenset[str]:
        normalized = table_name.casefold()
        for table in self.tables:
            if table.name.casefold() == normalized:
                return frozenset(column.name.casefold() for column in table.columns)
        return frozenset()

    def as_prompt_context(self) -> str:
        """Return a compact, deterministic schema description for a SQL generator."""
        lines: list[str] = []
        for table in self.tables:
            columns = ", ".join(
                f"{column.name} {column.data_type}" + (" PRIMARY KEY" if column.primary_key else "")
                for column in table.columns
            )
            lines.append(f"TABLE {table.name} ({columns})")
        return "\n".join(lines)
