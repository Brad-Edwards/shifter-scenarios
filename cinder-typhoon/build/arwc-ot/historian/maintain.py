"""Maintain native daily partitions and explicit historian storage bounds."""
import datetime as dt
import json
import logging
import pathlib
import sys
import time

import psycopg
from psycopg import sql

POLICY = json.loads((pathlib.Path(__file__).parent / "contract.json").read_text())["retention"]
LOG = logging.getLogger("history-maintenance")


def partitions(db):
    return db.execute("""SELECT c.relname FROM pg_inherits i
        JOIN pg_class c ON c.oid=i.inhrelid JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='ot_history' ORDER BY c.relname""").fetchall()


def maintain(db, today=None):
    today = today or dt.datetime.now(dt.timezone.utc).date()
    if not db.execute("SELECT pg_try_advisory_lock(366)").fetchone()[0]:
        return
    try:
        for table in ("process_samples", "command_signals"):
            for days in (0, 1):
                day = today + dt.timedelta(days=days)
                start = dt.datetime.combine(day, dt.time(), dt.timezone.utc)
                end = start + dt.timedelta(days=1)
                name = table + "_" + day.strftime("%Y%m%d")
                db.execute(sql.SQL("CREATE TABLE IF NOT EXISTS ot_history.{} PARTITION OF ot_history.{} FOR VALUES FROM ({}) TO ({})")
                    .format(sql.Identifier(name), sql.Identifier(table), sql.Literal(start), sql.Literal(end)))
        # Names are created here from fixed parent names and UTC dates only.
        removable = []
        for (name,) in partitions(db):
            parent, date = name.rsplit("_", 1)
            if parent not in ("process_samples", "command_signals") or len(date) != 8 or not date.isdigit():
                continue
            day = dt.datetime.strptime(date, "%Y%m%d").date()
            days = POLICY["process_days"] if parent == "process_samples" else POLICY["event_days"]
            expired = day < today - dt.timedelta(days=days-1)
            if expired:
                db.execute(sql.SQL("DROP TABLE ot_history.{}").format(sql.Identifier(name)))
                LOG.info("Removed expired historian partition %s", name)
            elif day < today:
                removable.append((day, parent != "process_samples", name))
        db.execute("DELETE FROM ot_history.alarm_events WHERE ontime < now()-(%s*interval '1 day')", (POLICY["event_days"],))
        for _, _, name in sorted(removable):
            size = db.execute("SELECT pg_database_size(current_database())").fetchone()[0]
            if size < POLICY["database_target_bytes"]:
                break
            db.execute(sql.SQL("DROP TABLE ot_history.{}").format(sql.Identifier(name)))
            LOG.warning("Removed oldest retained partition %s at database storage threshold", name)
        size = db.execute("SELECT pg_database_size(current_database())").fetchone()[0]
        if size >= POLICY["database_high_bytes"]:
            LOG.error("Historian capacity reached; ingestion guard active; inspect retention and provisioned disk")
        else:
            LOG.info("Historian maintenance complete; database_bytes=%s", size)
    finally:
        db.execute("SELECT pg_advisory_unlock(366)")


def main():
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            with psycopg.connect(autocommit=True, connect_timeout=10) as db:
                maintain(db)
        except psycopg.Error as error:
            LOG.error("Historian maintenance unavailable (%s)", type(error).__name__)
            if "--once" in sys.argv:
                raise
        if "--once" in sys.argv:
            return
        time.sleep(POLICY["maintenance_seconds"])


if __name__ == "__main__":
    main()
