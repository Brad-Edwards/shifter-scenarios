"""Read native acquisition counters and provenance; no process commands."""
import datetime as dt
import json
import pathlib
import sys
import time

import psycopg

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from project_config import write_json

ROOT = pathlib.Path("/slice")


def main():
    credentials = json.loads((ROOT / ".operator/credentials.json").read_text())
    with psycopg.connect(host="postgres", dbname="historian", user="reader", password=credentials["reader"]) as db:
        # The first post-restart measurement can precede the first field-quality
        # sample. Preserve that unknown interval and wait for native acquisition.
        deadline = time.monotonic() + 30
        while True:
            coverage = db.execute("SELECT count(DISTINCT tag),count(*),min(source_time),max(source_time) FROM process_history WHERE source_time>clock_timestamp()-interval '30 seconds'").fetchone()
            sample = db.execute("SELECT source_time,collected_time,ingested_at,value,transport_quality,process_quality,node_id,register_sha256 FROM process_history WHERE tag='level_m' AND source_time>clock_timestamp()-interval '3 seconds' ORDER BY source_time DESC LIMIT 1").fetchone()
            if coverage[0] == 50 and sample is not None and sample[0] <= sample[1] <= sample[2] and sample[4:6] == ("Good", "Good"):
                break
            if time.monotonic() >= deadline:
                raise RuntimeError("Native historian acquisition did not become ready within 30 seconds")
            time.sleep(1)
        qualities = dict(db.execute("SELECT process_quality,count(*) FROM process_history WHERE source_time>now()-interval '10 seconds' GROUP BY process_quality").fetchall())
        report = {"issue": 366, "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
                  "scope": "native installation and read-only acquisition counters; operating/reconnect/browser QA pending",
                  "live_tags": coverage[0], "recent_records": coverage[1], "quality_counts": qualities,
                  "sample": dict(zip(("source_time","collected_time","ingested_at","value","transport_quality","process_quality","node_id","register_sha256"), map(str,sample)))}
    write_json(ROOT / ".operator/history-installation.json", report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
