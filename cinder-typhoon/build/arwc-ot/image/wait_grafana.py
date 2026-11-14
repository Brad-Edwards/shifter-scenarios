"""Wait for Grafana's native health endpoint during fresh application setup."""
import time
import requests

deadline = time.monotonic() + 60
while True:
    try:
        requests.get("http://grafana:3000/api/health", timeout=3).raise_for_status()
        break
    except requests.RequestException:
        if time.monotonic() >= deadline:
            raise
        time.sleep(1)
