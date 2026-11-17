"""Render plain engineering lists from the authoritative site register."""
import csv
import json
import pathlib
import sys


def main():
    root = pathlib.Path(__file__).resolve().parents[1]
    register = json.loads((root / "site/tags.json").read_text())
    target = pathlib.Path(sys.argv[1])
    with (target / "io-list.csv").open("w", newline="") as stream:
        rows = csv.writer(stream)
        rows.writerow(["area", "zero_based_offset", "iec_address", "variable", "type", "meaning", "unit", "counts_per_unit"])
        for area in ("inputs", "discrete_inputs", "outputs", "coils"):
            for point in register["modbus"][area]:
                rows.writerow([area, point["offset"], point["iec"], point["variable"], point["type"], point["meaning"], point.get("unit", "boolean"), point.get("counts_per_unit", 1)])
    with (target / "opcua-tags.csv").open("w", newline="") as stream:
        rows = csv.writer(stream)
        rows.writerow(["variable", "type", "unit", "request_write", "owner", "node_id"])
        for tag in register["tags"]:
            rows.writerow([tag["variable"], tag["type"], tag["unit"], tag["write"], tag["owner"], f"nsu={register['namespace_uri']};s=CRR.{tag['variable']}"])


if __name__ == "__main__":
    main()
