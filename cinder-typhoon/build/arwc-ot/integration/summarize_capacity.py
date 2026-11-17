"""Summarize an explicitly selected resource record without copying private state."""
import argparse
import datetime as dt
import json
import pathlib
import statistics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=pathlib.Path)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.record.read_text().splitlines()]
    if len(rows) < 2:
        parser.error("At least two samples are required")
    elapsed = (dt.datetime.fromisoformat(rows[-1]["at"]) - dt.datetime.fromisoformat(rows[0]["at"])).total_seconds()
    if elapsed <= 0:
        parser.error("Samples must have increasing timestamps")
    cpu = [r["host_cpu_percent"] for r in rows if r["host_cpu_percent"] is not None]
    history = [r for r in rows if "historian_database_bytes" in r]
    result = {"label": rows[0]["label"], "start": rows[0]["at"], "end": rows[-1]["at"],
        "elapsed_seconds": round(elapsed, 1), "samples": len(rows),
        "logical_cpus": rows[0]["logical_cpus"],
        "host_cpu_mean_percent": round(statistics.mean(cpu), 2) if cpu else None,
        "host_cpu_peak_percent": round(max(cpu), 2) if cpu else None,
        "memory_total_bytes": rows[0]["memory_total_bytes"],
        "memory_available_min_bytes": min(r["memory_available_bytes"] for r in rows),
        "disk_available_min_bytes": min(r["disk_available_bytes"] for r in rows),
        "container_names": sorted({c["Name"] for r in rows for c in r.get("containers", [])}),
        "measurement_errors": [r["measurement_error"] for r in rows if "measurement_error" in r],
        "scope": "Observed workload only; correlate with QA and native PLC timing before capacity acceptance"}
    if len(history) >= 2:
        seconds = (dt.datetime.fromisoformat(history[-1]["at"])-dt.datetime.fromisoformat(history[0]["at"])).total_seconds()
        result["historian_start_bytes"] = history[0]["historian_database_bytes"]
        result["historian_end_bytes"] = history[-1]["historian_database_bytes"]
        result["historian_growth_bytes_per_hour"] = round((history[-1]["historian_database_bytes"]-history[0]["historian_database_bytes"])*3600/seconds)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
