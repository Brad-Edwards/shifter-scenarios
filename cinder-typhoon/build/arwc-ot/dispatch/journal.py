"""Durable request identity and distinct command-transition records."""
from psycopg.types.json import Jsonb

from model import CONTRACT, fingerprint


def receive(db, request):
    """Return (new, state). Caller acknowledges MQTT only after commit."""
    digest = fingerprint(request)
    with db.transaction():
        row = db.execute("""INSERT INTO ot_dispatch.requests(id,fingerprint,request,principal,status)
            VALUES (%s,%s,%s,%s,'received') ON CONFLICT DO NOTHING RETURNING id""",
            (request["id"], digest, Jsonb(request), CONTRACT["principal"])).fetchone()
        if row:
            db.execute("INSERT INTO ot_dispatch.transitions(request_id,status,detail) VALUES (%s,'received',%s)",
                (request["id"], Jsonb({"origin": "durable dispatcher receipt"})))
            return True, {"id": request["id"], "status": "received"}
        row = db.execute("SELECT fingerprint,status,detail,sequence FROM ot_dispatch.requests WHERE id=%s", (request["id"],)).fetchone()
        if row[0] != digest:
            return False, {"id": request["id"], "status": "conflict", "duplicate": True}
        return False, {"id": request["id"], "status": row[1], "detail": row[2], "sequence": row[3], "duplicate": True}


def transition(db, identifier, status, detail=None):
    if status not in CONTRACT["states"]:
        raise ValueError("Unknown dispatcher state")
    detail = detail or {}
    with db.transaction():
        current = db.execute("SELECT status,detail,sequence FROM ot_dispatch.requests WHERE id=%s FOR UPDATE", (identifier,)).fetchone()
        if current is None:
            raise ValueError("Unknown request ID")
        if current[0] in CONTRACT["terminal"]:
            return {"id": identifier, "status": current[0], "detail": current[1], "sequence": current[2]}
        db.execute("""UPDATE ot_dispatch.requests SET status=%s,detail=%s,
            sequence=coalesce(%s,sequence),updated_at=clock_timestamp() WHERE id=%s""",
            (status, Jsonb(detail), detail.get("sequence"), identifier))
        db.execute("INSERT INTO ot_dispatch.transitions(request_id,status,detail) VALUES (%s,%s,%s)",
            (identifier, status, Jsonb(detail)))
    return {"id": identifier, "status": status, "detail": detail}


def reconcile_restart(db):
    # The session-level writer lock is acquired before this function runs.
    with db.transaction():
        rows = db.execute("""UPDATE ot_dispatch.requests SET status='uncertain',
            detail='{"reason":"dispatcher restart; operator reconciliation required"}',updated_at=clock_timestamp()
            WHERE status IN ('received','dispatch_intent','dispatched','plc_accepted') RETURNING id""").fetchall()
        for (identifier,) in rows:
            db.execute("INSERT INTO ot_dispatch.transitions(request_id,status,detail) VALUES (%s,'uncertain',%s)",
                (identifier, Jsonb({"reason": "dispatcher restart; never automatically replay"})))
    return len(rows)
