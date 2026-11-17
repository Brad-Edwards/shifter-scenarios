"""Verify setup preserves platform credentials and participant work."""
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
    spec = importlib.util.spec_from_file_location("test_provision", HERE / "test_provision.py")
    tests = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tests)

    def run():
        with contextlib.redirect_stdout(io.StringIO()):
            return unittest.TextTestRunner(stream=io.StringIO()).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(tests.ProvisionTests))

    result = run()
    if not result.wasSuccessful():
        raise RuntimeError(str(result.errors + result.failures))
    source = (HERE / "provision.py").read_text()
    mutations = [
        ('    credentials = json.loads((PRIVATE / "credentials.json").read_text())',
         '    docker("exec", CONTAINER, "chpasswd")\n    credentials = json.loads((PRIVATE / "credentials.json").read_text())'),
        ('if exists.returncode:', 'if not exists.returncode:'),
        ('    credentials = json.loads((PRIVATE / "credentials.json").read_text())',
         '    (PRIVATE / "workstation-credentials.json").write_text("{}")\n    credentials = json.loads((PRIVATE / "credentials.json").read_text())'),
    ]
    for before, after in mutations:
        if source.count(before) != 1:
            raise ValueError("Setup mutation target changed")
        module = types.ModuleType("provision_mutation")
        module.__file__ = str(HERE / "provision.py")
        exec(compile(source.replace(before, after), module.__file__, "exec"), module.__dict__)
        tests.provision = module
        if run().wasSuccessful():
            raise RuntimeError("A credential or participant-state mutation survived")
    print(json.dumps({"setup_boundary_cases": result.testsRun, "status": "passed", "mutations_detected": len(mutations)}))


if __name__ == "__main__":
    main()
