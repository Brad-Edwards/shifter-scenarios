"""Run real IEC block tests and focused mutations with STruC++ on the VM."""
import hashlib
import json
import pathlib
import socket
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent
BUILD = ROOT.parent / ".operator/controller-tests"
COMPILER = ROOT.parent / ".operator/compiler/strucpp/strucpp"
SOURCES = ("SiteInputs.st", "SiteRequests.st", "OutletControl.st")
# Native 0.7.0 ADVANCE_TIME is supported at the test's top level only.
# Unroll 40 seconds of physical feedback, retaining actual TON and PID execution.
AUTO_SCAN = """
  g(AutoMode := TRUE, FlowSetting := 0.2, PositionRaw := REAL_TO_UINT(MeasuredPosition*100.0),
    FlowRaw := REAL_TO_UINT(MeasuredPosition*50.0));
  MeasuredPosition := Position;
  IF DriveEnabled THEN
    Difference := DriveTarget - Position;
    Position := Position + LIMIT(-0.5, Difference, 0.5);
  END_IF;
  DriveEnabled := g.EnableCoil;
  DriveTarget := UINT_TO_REAL(g.TargetRaw)/100.0;
  ADVANCE_TIME(T#100ms);
"""
MUTATIONS = (
    ("level_scaling", "SiteInputs.st", "UINT_TO_REAL(LevelRaw) / 1000.0", "UINT_TO_REAL(LevelRaw) / 100.0"),
    ("local_priority", "SiteRequests.st", "IF HmiNew THEN", "IF HmiNew AND NOT RemoteNew THEN"),
    ("remote_enable", "SiteRequests.st", "(CandidateSource = 2) AND NOT RemoteEnabled", "(CandidateSource = 2) AND FALSE"),
    ("no_replay", "SiteRequests.st", "RemoteSeen := RemoteSequence;", "RemoteSeen := 0;"),
    ("field_permissive", "OutletControl.st", "EnableCoil := Armed AND Permissive AND", "EnableCoil := Armed AND"),
    ("low_level_close", "OutletControl.st", "IF LowLevel THEN\n  EffectiveTarget := 0.0;", "IF LowLevel THEN\n  EffectiveTarget := ManualTarget;"),
    ("travel_timeout", "OutletControl.st", "PT := T#25s", "PT := T#250s"),
    ("reversal_delay", "OutletControl.st", "PT := T#500ms", "PT := T#0ms"),
    ("flow_deadband", "OutletControl.st", "AND Regulating AND NOT Saturated", "AND NOT Saturated"),
    ("closed_endpoint", "OutletControl.st", "IF TargetRaw = 0 THEN", "IF FALSE THEN"),
)


def run_case(name, sources, test_file):
    directory = BUILD / name
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for filename, content in sources.items():
        path = directory / filename
        path.write_text(content)
        paths.append(str(path))
    result = subprocess.run([str(COMPILER), *paths, "-o", str(directory / "controller.cpp"), "--cxx-flags", "-std=c++17", "--test", str(test_file)], cwd=directory, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
    (directory / "result.log").write_text(result.stdout)
    print(f"{name}: exit {result.returncode}", flush=True)
    return result


def main():
    if socket.gethostname() != "cinder-arwc-ot-compat-363":
        raise RuntimeError("Run controller checks on the dedicated VM")
    BUILD.mkdir(parents=True, exist_ok=True)
    template = (ROOT / "test_controller.st.in").read_text()
    assert template.count("{{AUTO_SCANS}}") == 1
    assert template.count("{{AUTO_QUIET_SCANS}}") == 1
    tests = BUILD / "test_controller.st"
    tests.write_text(template.replace("{{AUTO_SCANS}}", AUTO_SCAN * 400).replace("{{AUTO_QUIET_SCANS}}", (AUTO_SCAN+"\n  ASSERT_FALSE(g.EnableCoil, 'Automatic flow must remain settled');\n")*50))
    sources = {name: (ROOT / name).read_text() for name in SOURCES}
    baseline = run_case("baseline", sources, tests)
    if baseline.returncode:
        print(baseline.stdout[-10000:])
        raise SystemExit("Controller baseline failed")
    # A mutant counts only if it compiles and an assertion catches its behavior.
    killed = []
    for name, filename, before, after in MUTATIONS:
        assert sources[filename].count(before) == 1, f"Non-unique mutation anchor: {name}"
        mutant = dict(sources)
        mutant[filename] = mutant[filename].replace(before, after)
        result = run_case(name, mutant, tests)
        if result.returncode == 0 or "[FAIL]" not in result.stdout:
            print(result.stdout[-10000:])
            raise AssertionError(f"Mutation {name} survived or did not reach a test assertion")
        killed.append(name)
    evidence = {"scope":"Native IEC controller blocks; normal control decisions", "compiler":"STruC++ 0.7.0",
        "baseline":"passed", "mutations_detected":killed,
        "source_sha256":{name:hashlib.sha256(content.encode()).hexdigest() for name,content in sources.items()}}
    (BUILD / "evidence.json").write_text(json.dumps(evidence,indent=2)+"\n")
    print(json.dumps(evidence,indent=2))


if __name__ == "__main__":
    main()
