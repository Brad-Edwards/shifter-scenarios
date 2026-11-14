"""Copy native FUXA alarm history; never infer alarm state from measurements."""
import datetime as dt
import logging
import os
import time

import psycopg
import requests

LOG = logging.getLogger("alarm-export")
URL = "http://fuxa:1881"


def timestamp(value):
    return dt.datetime.fromtimestamp(float(value)/1000, dt.timezone.utc) if value else None


def export(session, db):
    response = session.get(URL + "/api/alarmsHistory", params={"start": int((time.time()-30*86400)*1000), "end": int(time.time()*1000)}, timeout=15)
    if response.status_code in (401, 403):
        raise PermissionError("FUXA session requires renewal")
    response.raise_for_status()
    records = response.json()
    for alarm in records:
        if not alarm.get("name") or not alarm.get("ontime"):
            continue
        db.execute('''INSERT INTO ot_history.alarm_events
            (name,type,ontime,offtime,acktime,acknowledging_user,text,alarm_group,value,native_status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (name,type,ontime) DO UPDATE SET
              offtime=EXCLUDED.offtime,acktime=EXCLUDED.acktime,acknowledging_user=EXCLUDED.acknowledging_user,
              value=EXCLUDED.value,native_status=EXCLUDED.native_status,observed_at=clock_timestamp()
            WHERE (alarm_events.offtime,alarm_events.acktime,alarm_events.acknowledging_user,alarm_events.value,alarm_events.native_status)
              IS DISTINCT FROM (EXCLUDED.offtime,EXCLUDED.acktime,EXCLUDED.acknowledging_user,EXCLUDED.value,EXCLUDED.native_status)''',
            (alarm["name"], alarm["type"], timestamp(alarm["ontime"]), timestamp(alarm.get("offtime")),
             timestamp(alarm.get("acktime")), alarm.get("userack"), alarm.get("text"), alarm.get("group"),
             str(alarm["value"]) if alarm.get("value") is not None else None, alarm.get("status")))
    return len(records)


def main():
    logging.basicConfig(level=logging.INFO)
    session = requests.Session()
    while True:
        try:
            if "x-access-token" not in session.headers:
                response = session.post(URL + "/api/signin", json={"username": "history-export", "password": os.environ["FUXA_PASSWORD"]}, timeout=10)
                response.raise_for_status()
                session.headers["x-access-token"] = response.json()["data"]["token"]
            with psycopg.connect(autocommit=True, connect_timeout=10) as db:
                count = export(session, db)
            LOG.info("Native FUXA alarm history synchronized; records=%s", count)
        except PermissionError:
            session.headers.pop("x-access-token", None)
        except (requests.RequestException, psycopg.Error, ValueError, KeyError) as error:
            LOG.error("Native alarm history export unavailable (%s)", type(error).__name__)
            session.headers.pop("x-access-token", None)
        time.sleep(5)


if __name__ == "__main__":
    main()
