"""Targeted native document contract checks; run on the development VM."""
import copy
import json
import re
import unittest

from build_project import HERE, OPERATE, build_project, validate_project


class ProjectContract(unittest.TestCase):
    def setUp(self):
        self.model = json.loads((HERE / "views.json").read_text())
        self.register = json.loads((HERE / "../site/tags.json").read_text())
        self.project = build_project({}, 7)

    def test_real_namespace_and_four_views(self):
        self.assertEqual(len(self.project["hmi"]["views"]), 4)
        self.assertEqual(len(self.project["devices"]["crr-plc"]["tags"]), 50)
        self.assertTrue(all(t["address"].startswith("ns=7;") for t in self.project["devices"]["crr-plc"]["tags"].values()))

    def test_mutated_permission_and_binding_contracts(self):
        # Each mutation breaks a different participant-facing boundary.
        def mutate_control(project):
            for view in project["hmi"]["views"]:
                for item in view["items"].values():
                    if not item["property"]["readonly"]:
                        item["property"]["permission"] = OPERATE | 1
                        return

        def mutate_binding(project):
            item = next(iter(project["hmi"]["views"][0]["items"].values()))
            item["property"]["variableId"] = "InventedMeasurement"

        def mutate_alarm(project):
            project["alarms"][0]["property"]["permission"] |= 1

        def mutate_script(project):
            project["scripts"][0]["permission"] = 3

        def mutate_history(project):
            project["devices"]["crr-plc"]["tags"]["LevelM"]["daq"]["enabled"] = True

        def mutate_alarm_delay(project):
            project["alarms"][0]["high"]["checkdelay"] = 1000

        def mutate_html_control(project):
            view = project["hmi"]["views"][0]
            view["svgcontent"] = view["svgcontent"].replace('<select xmlns=', '<html:select xmlns:html="http://www.w3.org/1999/xhtml" xmlns=').replace('</select>', '</html:select>')

        def mutate_select_closing_tag(project):
            view = project["hmi"]["views"][0]
            view["svgcontent"] = re.sub(r'(<select\b[^>]*?)></select>', r'\1/>', view["svgcontent"])

        def mutate_script_mode(project):
            project["scripts"][0]["mode"] = "server"

        for mutate in (mutate_control, mutate_binding, mutate_alarm, mutate_script, mutate_history, mutate_alarm_delay, mutate_html_control, mutate_select_closing_tag, mutate_script_mode):
            project = copy.deepcopy(self.project)
            mutate(project)
            with self.subTest(mutation=mutate.__name__), self.assertRaises(AssertionError):
                validate_project(project, self.model, self.register)


if __name__ == "__main__":
    unittest.main()
