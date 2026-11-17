"""Real PostgreSQL request retry and restart checks, all rolled back."""
import json
import pathlib
import types

import psycopg

from journal import receive, reconcile_restart, transition
from model import parse_request
from test_model import REQUEST

ROOT = pathlib.Path("/slice")
HERE = pathlib.Path(__file__).parent


def main():
    credentials = json.loads((ROOT / ".operator/credentials.json").read_text())
    with psycopg.connect(host="postgres", dbname="historian", user="historian", password=credentials["postgres"]) as db:
        db.execute((HERE / "schema.sql").read_text())
        request = parse_request(json.dumps(REQUEST).encode())
        new, _ = receive(db, request)
        assert new
        new, outcome = receive(db, request)
        assert not new and outcome["status"] == "received"
        new, outcome = receive(db, dict(request, position_a_pct=30))
        assert not new and outcome["status"] == "conflict"
        assert db.execute("SELECT count(*) FROM ot_dispatch.transitions WHERE request_id=%s", (request["id"],)).fetchone()[0] == 1
        transition(db, request["id"], "dispatched", {"sequence": 1})
        assert reconcile_restart(db) >= 1
        new, outcome = receive(db, request)
        assert not new and outcome["status"] == "uncertain"
        # A later error must not overwrite an already terminal outcome.
        assert transition(db, request["id"], "completed")["status"] == "uncertain"
        mutations = [
            ('if row[0] != digest:', 'if False:'),
            ('if current[0] in CONTRACT["terminal"]:', 'if False:'),
        ]
        for index, (before, after) in enumerate(mutations):
            mutant = types.ModuleType("mutated_journal")
            source = (HERE / "journal.py").read_text()
            assert before in source
            exec(compile(source.replace(before, after), str(HERE / "journal.py"), "exec"), mutant.__dict__)
            if index == 0:
                _, result = mutant.receive(db, dict(request, position_a_pct=30))
                assert result["status"] != "conflict"
            else:
                result = mutant.transition(db, request["id"], "completed")
                assert result["status"] != "uncertain"
        db.rollback()
    print(json.dumps({"duplicate_no_redispatch": "passed", "changed_payload_conflict": "passed",
                      "restart_no_replay": "passed", "terminal_outcome_preserved": "passed",
                      "journal_mutations_detected": len(mutations), "fixture_records_committed": 0}))


if __name__ == "__main__":
    main()
