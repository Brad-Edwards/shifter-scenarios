import copy
import unittest
import yaml
from validate import ROOT, load_compose, validate, validate_dmz


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.document = load_compose()

    def test_contract(self):
        validate(self.document)

    def test_backend_cannot_join_supervisory(self):
        changed = copy.deepcopy(self.document)
        changed["services"]["backend"]["networks"].append("supervisory")
        with self.assertRaises(AssertionError):
            validate(changed)

    def test_edge_cannot_forward(self):
        changed = copy.deepcopy(self.document)
        changed["services"]["edge"]["sysctls"] = {"net.ipv4.ip_forward": "1"}
        with self.assertRaises(AssertionError):
            validate(changed)

    def test_backend_cannot_publish_host_port(self):
        changed = copy.deepcopy(self.document)
        changed["services"]["backend"]["ports"] = ["8000:8000"]
        with self.assertRaises(AssertionError):
            validate(changed)

    def test_dmz_contract(self):
        validate_dmz(yaml.safe_load((ROOT / "dmz.compose.yaml").read_text()))

    def test_renderer_cannot_join_corporate_data(self):
        changed = yaml.safe_load((ROOT / "dmz.compose.yaml").read_text())
        changed["services"]["renderer"]["networks"]["data"] = {}
        with self.assertRaises(AssertionError):
            validate_dmz(changed)

    def test_dmz_reader_cannot_expose_public_schema(self):
        changed = yaml.safe_load((ROOT / "dmz.compose.yaml").read_text())
        changed["services"]["postgrest"]["environment"]["PGRST_DB_SCHEMAS"] = "public"
        with self.assertRaises(AssertionError):
            validate_dmz(changed)


if __name__ == "__main__":
    unittest.main()
