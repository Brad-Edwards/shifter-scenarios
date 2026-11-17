"""Focused request/feedback developer checks; no broker or PLC connections."""
import json
import pathlib
import unittest

import model

HERE = pathlib.Path(__file__).parent
REQUEST = {"id": "00000000-0000-4000-8000-000000000367", "asset": "AST-CRR-017", "mode": "manual",
           "position_a_pct": 25, "position_b_pct": 15, "total_flow_m3s": 0.4, "expires_at": 1060}
STATE = {"IoHealthy": True, "Owner": 2, "AutoMode": False, "PermissiveA": True, "PermissiveB": True,
         "MovingA": False, "MovingB": False, "PositionPct": 25, "PositionBPct": 15,
         "RequestedTargetPct": 25, "RequestedTargetBPct": 15, "RequestedFlowM3s": 0.4,
         "FlowM3s": 0.125, "FlowBM3s": 0.075}


def checks(module):
    request = module.parse_request(json.dumps(REQUEST).encode())
    assert module.fingerprint(request) == module.fingerprint(dict(reversed(list(request.items()))))
    for change in ({"asset": "another-site"}, {"principal": "someone-else"}, {"position_a_pct": 101},
                   {"position_b_pct": -1}, {"total_flow_m3s": float("nan")}, {"mode": "unknown"}, {"id": None}):
        invalid = dict(REQUEST, **change)
        try:
            module.parse_request(json.dumps(invalid).encode())
        except (ValueError, TypeError):
            pass
        else:
            raise AssertionError("Invalid request accepted")
    assert module.next_sequence(0) == 1 and module.next_sequence(65535) == 1
    for invalid in (None, True, -1, 65536):
        try:
            module.next_sequence(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid PLC sequence accepted")
    assert module.dispatchable(request, 1000)
    assert not module.dispatchable(request, 1060)
    assert not module.dispatchable(request, 900)
    assert module.completion(request, STATE)
    for change in ({"IoHealthy": False}, {"Owner": 1}, {"PositionBPct": 40}, {"RequestedTargetBPct": 40},
                   {"MovingA": True}, {"PermissiveB": False}, {"AutoMode": True}):
        assert not module.completion(request, dict(STATE, **change)), change
    automatic = dict(request, mode="automatic")
    state = dict(STATE, AutoMode=True, FlowM3s=0.2, FlowBM3s=0.2)
    assert module.completion(automatic, state)
    assert not module.completion(automatic, dict(state, FlowBM3s=0.3))
    zero = dict(automatic, total_flow_m3s=0)
    closed = dict(state, RequestedFlowM3s=0, PositionPct=0, PositionBPct=0, FlowM3s=0, FlowBM3s=0)
    assert module.completion(zero, closed)
    assert not module.completion(zero, dict(closed, PositionBPct=0.4))
    assert not module.completion(zero, dict(closed, RequestedFlowM3s=0.4))


class RequestAndFeedback(unittest.TestCase):
    def test_request_sequence_and_feedback_contract(self):
        checks(model)

    def test_mutations_are_detected(self):
        source = (HERE / "model.py").read_text()
        mutations = [
            ('request["asset"] != CONTRACT["asset"]', 'False'),
            ('set(request) != set(CONTRACT["request_fields"])', 'False'),
            ('request["position_a_pct"] <= 100', 'request["position_a_pct"] <= 1000'),
            ('not state["IoHealthy"]', 'False'),
            ('abs(state["PositionBPct"]-request["position_b_pct"]) <= limits["position_tolerance_pct"]', 'True'),
            ('state["PositionBPct"] <= 0.05', 'True'),
            ('abs(state["RequestedFlowM3s"]-request["total_flow_m3s"]) > 0.0001', 'False'),
            ('CONTRACT["maximum_expiry_seconds"]', '1200'),
        ]
        import types
        for before, after in mutations:
            assert before in source
            mutant = types.ModuleType("mutated_request_model")
            mutant.__file__ = str(HERE / "model.py")
            exec(compile(source.replace(before, after), mutant.__file__, "exec"), mutant.__dict__)
            with self.subTest(mutation=before), self.assertRaises(AssertionError):
                checks(mutant)


if __name__ == "__main__":
    unittest.main()
