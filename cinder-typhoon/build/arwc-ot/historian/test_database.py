"""Developer SQL regression fixtures; every fixture and mutation is rolled back."""
import datetime as dt
import json
import pathlib

import psycopg
from psycopg.types.json import Jsonb

from maintain import maintain

ROOT = pathlib.Path("/slice")
GOOD = "The operation succeeded. StatusGood (0x0)"


def fixture(db, index, quality=GOOD, healthy=True, age=0.1, missing=False):
    source = dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(seconds=index*10)
    collected = int((source.timestamp()+age)*1e9)
    for variable, series, value in [("IoHealthy", "io_healthy", healthy), ("LevelM", "level_m", 8.0)]:
        fields = {"value": value, "Quality": quality, "collected_at_ns": collected}
        if missing and variable == "LevelM":
            fields.pop("collected_at_ns")
        db.execute("INSERT INTO ot_history.process_samples(time,tags,fields) VALUES (%s,%s,%s)",
            (source, Jsonb({"asset": "ARWC-DEVELOPER-FIXTURE", "variable": variable, "series": series, "unit": "m"}), Jsonb(fields)))
    return source


def classifications(db):
    return [r[0] for r in db.execute("SELECT process_quality FROM process_history WHERE asset='ARWC-DEVELOPER-FIXTURE' AND tag='level_m' ORDER BY source_time")]


def main():
    credentials = json.loads((ROOT / ".operator/credentials.json").read_text())
    source = (ROOT / "historian/views.sql").read_text()
    with psycopg.connect(host="postgres", dbname="historian", user="historian", password=credentials["postgres"]) as db:
        # These uncommitted rows are never visible to QA or native products.
        fixture(db, 0)
        fixture(db, 1, healthy=False)
        fixture(db, 2, quality="BadCommunicationError")
        fixture(db, 3, age=4)
        fixture(db, 4, missing=True)
        expected = ["Good", "FieldUnavailable", "BadTransport", "Stale", "Unknown"]
        assert classifications(db) == expected, classifications(db)
        killed = 0
        for before, after in [("q.value = 1", "q.value = 0"), ("interval '3 seconds'", "interval '30 seconds'"),
                              ("m.collected_time IS NULL OR m.value IS NULL", "m.value IS NULL")]:
            assert before in source
            db.execute(source.replace(before, after))
            assert classifications(db) != expected, "Quality mutation escaped"
            killed += 1
            db.execute(source)
        # A failed capacity check must prevent an insert, without changing data.
        try:
            with db.transaction():
                db.execute("""CREATE OR REPLACE FUNCTION ot_history.check_capacity() RETURNS trigger LANGUAGE plpgsql
                    AS $$ BEGIN RAISE EXCEPTION 'Developer capacity fixture' USING ERRCODE='53100'; END $$""")
                fixture(db, 5)
        except psycopg.errors.DiskFull:
            pass
        else:
            raise AssertionError("Capacity guard did not stop the write")
        db.rollback()
    # Exercise real native partition retention inside another rollback boundary.
    with psycopg.connect(host="postgres", dbname="historian", user="historian", password=credentials["postgres"]) as db:
        db.execute("""CREATE TABLE ot_history.process_samples_20200101 PARTITION OF ot_history.process_samples
            FOR VALUES FROM ('2020-01-01T00:00:00Z') TO ('2020-01-02T00:00:00Z')""")
        maintain(db, today=dt.date(2020, 1, 10))
        assert db.execute("SELECT to_regclass('ot_history.process_samples_20200101')").fetchone()[0] is None
        assert db.execute("SELECT to_regclass('ot_history.process_samples_20200110')").fetchone()[0] is not None
        db.rollback()
    print(json.dumps({"quality_cases": 5, "quality_mutations_killed": killed, "capacity_guard": "passed",
                      "native_partition_retention": "passed", "fixture_records_committed": 0}))


if __name__ == "__main__":
    main()
