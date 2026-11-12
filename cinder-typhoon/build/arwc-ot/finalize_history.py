"""Expose source time, ingestion time, transport status and field freshness."""
import json
import pathlib

import psycopg
from psycopg import sql

ROOT = pathlib.Path("/slice")


def main() -> None:
    credentials = json.loads((ROOT / ".operator/credentials.json").read_text())
    register = json.loads((ROOT / "tags.json").read_text())
    with psycopg.connect(host="postgres", dbname="historian", user="historian", password=credentials["postgres"], autocommit=True) as db:
        for tag in register["tags"]:
            table = sql.Identifier(tag["table"])
            # Keep pre-migration ingestion time unknown; never backfill invented times.
            db.execute(sql.SQL("ALTER TABLE {} ADD COLUMN IF NOT EXISTS ingested_at timestamptz").format(table))
            db.execute(sql.SQL("ALTER TABLE {} ALTER COLUMN ingested_at SET DEFAULT clock_timestamp()").format(table))
        parts = []
        for name in ("level_m", "position_pct", "flow_m3s"):
            parts.append(sql.SQL('''SELECT m.time AT TIME ZONE 'UTC' AS source_time, m.ingested_at, m.asset,
                {}::text AS tag, m.unit, m.value,
                CASE WHEN m."Quality" IN ('Good', 'The operation succeeded. StatusGood (0x0)') THEN 'Good' ELSE m."Quality" END AS transport_quality,
                CASE WHEN m."Quality" IN ('Good', 'The operation succeeded. StatusGood (0x0)') AND q.value
                     AND q."Quality" IN ('Good', 'The operation succeeded. StatusGood (0x0)')
                     THEN 'Good' ELSE 'FieldUnavailable' END AS process_quality
                FROM {} m LEFT JOIN LATERAL
                (SELECT value, "Quality" FROM io_healthy q WHERE q.time <= m.time
                 AND q.time >= m.time - interval '2 seconds' ORDER BY q.time DESC LIMIT 1) q ON true''').format(sql.Literal(name), sql.Identifier(name)))
        # Rebuild this derived development view; raw records are never rewritten.
        db.execute("DROP VIEW IF EXISTS process_history")
        db.execute(sql.SQL("CREATE VIEW process_history AS ") + sql.SQL(" UNION ALL ").join(parts))
        db.execute("GRANT SELECT ON process_history TO reader")
    print("History exposes real source/ingestion times and separate transport/field quality.")


if __name__ == "__main__":
    main()
