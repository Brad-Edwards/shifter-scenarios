"""Run focused bridge checks and small boundary mutations on the build VM."""
import importlib.util
import io
import json
import pathlib
import socket
import types
import unittest

HERE = pathlib.Path(__file__).resolve().parent


def main():
    if socket.gethostname() != "cinder-arwc-ot-compat-363":
        raise SystemExit("Use the approved development VM")
    spec = importlib.util.spec_from_file_location("test_bridge", HERE / "test_bridge.py")
    tests = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tests)

    def run():
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(tests.BridgeTests)
        return unittest.TextTestRunner(stream=io.StringIO()).run(suite)

    original = tests.bridge
    result = run()
    if not result.wasSuccessful():
        raise RuntimeError(str(result.errors + result.failures))
    source = tests.SOURCE.read_text()
    mutations = [
        ("hmac.compare_digest(supplied, expected)", "True"),
        ("if not authorized(", "if False and not authorized("),
        ("LIMIT 900", "LIMIT 9000"),
        ("interval '5 minutes'", "interval '50 minutes'"),
        ("FROM public.dmz_process_history", "FROM public.process_history"),
        ("default_transaction_read_only=on", "default_transaction_read_only=off"),
        ("statement_timeout=2000", "statement_timeout=20000"),
        ("timeout=5,", "timeout=500,"),
    ]
    for before, after in mutations:
        if source.count(before) != 1:
            raise ValueError("Mutation target changed: " + before)
        module = types.ModuleType("bridge_mutation")
        exec(compile(source.replace(before, after), str(tests.SOURCE), "exec"), module.__dict__)
        tests.bridge = module
        if run().wasSuccessful():
            raise RuntimeError("An operating bridge boundary mutation survived: " + before)
    tests.bridge = original
    print(json.dumps({"focused_bridge_cases": result.testsRun, "status": "passed", "mutations_detected": len(mutations)}))


if __name__ == "__main__":
    main()
