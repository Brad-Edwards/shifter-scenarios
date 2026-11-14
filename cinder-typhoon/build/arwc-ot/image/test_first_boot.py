"""Check fresh/restart state and readiness ordering without a live range."""
import importlib.util
import pathlib
import tempfile
import unittest
from unittest.mock import patch

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("arwc_first_boot", HERE / "first_boot.py")
boot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boot)


class FirstBootTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = pathlib.Path(self.directory.name)
        self.state, self.ready = root / "state/initialized", root / "run/ready"
        for name, value in (("STATE", self.state), ("READY", self.ready)):
            p = patch.object(boot, name, value)
            p.start()
            self.addCleanup(p.stop)

    def test_fresh_range_is_not_complete_before_native_readiness(self):
        def check_readiness():
            self.assertFalse(self.state.exists())
            self.assertFalse(self.ready.exists())
        with patch.object(boot, "initialize") as initialize, patch.object(boot, "start_it"), \
                patch.object(boot, "readiness", side_effect=check_readiness) as readiness:
            boot.complete()
        initialize.assert_called_once_with()
        readiness.assert_called_once_with()
        self.assertTrue(self.state.exists())
        self.assertTrue(self.ready.exists())

    def test_restart_preserves_existing_application_state(self):
        self.state.parent.mkdir()
        self.state.write_text("existing initialized state")
        with patch.object(boot, "initialize") as initialize, patch.object(boot, "start_it"), \
                patch.object(boot, "readiness"), patch.object(boot, "compose") as compose:
            boot.complete()
        initialize.assert_not_called()
        compose.assert_called_once_with("up", "-d", "--no-build", joined=True)
        self.assertEqual(self.state.read_text(), "existing initialized state")

    def test_failed_initialization_does_not_publish_readiness(self):
        with patch.object(boot, "initialize", side_effect=RuntimeError("fixture failure")), \
                patch.object(boot, "readiness") as readiness:
            with self.assertRaises(RuntimeError):
                boot.complete()
        readiness.assert_not_called()
        self.assertFalse(self.state.exists())
        self.assertFalse(self.ready.exists())

    def test_failed_native_readiness_does_not_mark_fresh_initialization_complete(self):
        with patch.object(boot, "initialize"), patch.object(boot, "start_it"), \
                patch.object(boot, "readiness", side_effect=RuntimeError("fixture failure")):
            with self.assertRaises(RuntimeError):
                boot.complete()
        self.assertFalse(self.state.exists())
        self.assertFalse(self.ready.exists())


if __name__ == "__main__":
    unittest.main()
