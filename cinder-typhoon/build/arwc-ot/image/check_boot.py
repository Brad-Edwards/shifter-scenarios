"""Run isolated first-boot state tests and focused readiness mutations."""
import contextlib
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
    spec = importlib.util.spec_from_file_location("test_first_boot", HERE / "test_first_boot.py")
    tests = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tests)

    def run():
        with contextlib.redirect_stdout(io.StringIO()):
            return unittest.TextTestRunner(stream=io.StringIO()).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(tests.FirstBootTests))

    result = run()
    if not result.wasSuccessful():
        raise RuntimeError(str(result.errors + result.failures))
    source = (HERE / "first_boot.py").read_text()
    mutations = [
        ("if STATE.exists():", "if not STATE.exists():"),
        ("    readiness()\n    STATE.parent.mkdir", "    STATE.parent.mkdir(parents=True, exist_ok=True)\n    STATE.touch()\n    readiness()\n    STATE.parent.mkdir"),
        ("    readiness()\n    STATE.parent.mkdir", "    STATE.parent.mkdir"),
    ]
    for before, after in mutations:
        if source.count(before) != 1:
            raise ValueError("First-boot mutation target changed")
        module = types.ModuleType("boot_mutation")
        module.__file__ = str(HERE / "first_boot.py")
        exec(compile(source.replace(before, after), module.__file__, "exec"), module.__dict__)
        tests.boot = module
        if run().wasSuccessful():
            raise RuntimeError("A first-boot state or readiness mutation survived")
    print(json.dumps({"first_boot_state_cases": result.testsRun, "status": "passed", "mutations_detected": len(mutations)}))


if __name__ == "__main__":
    main()
