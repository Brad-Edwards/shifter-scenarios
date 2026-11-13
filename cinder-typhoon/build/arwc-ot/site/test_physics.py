"""Focused physical-response checks; execute in the VM's existing tools image."""
import pathlib
import tempfile
import unittest

from remote_io import Equipment


class PhysicalResponseTests(unittest.TestCase):
    def test_twenty_second_stroke_and_reservoir_mass_balance(self):
        plant = Equipment()
        for _ in range(200):
            plant.advance(0.1,[10000,10000],[True,True],[False,False])
        self.assertAlmostEqual(plant.positions[0],100.0)
        self.assertAlmostEqual(plant.positions[1],100.0)
        # Each linear 0->0.5 m3/s ramp passes 5 m3; inflow supplies 4 m3.
        loss_m3 = (8.0-plant.level_m)*2000
        self.assertAlmostEqual(loss_m3,6.0,delta=0.06)

    def test_disabled_actuator_holds_position_while_water_still_flows(self):
        plant = Equipment(positions=[40.0,20.0])
        flows = plant.advance(1.0,[0,0],[False,False],[False,False])
        self.assertEqual(plant.positions,[40.0,20.0])
        self.assertAlmostEqual(sum(flows),0.3)
        self.assertAlmostEqual((8.0-plant.level_m)*2000,0.1)

    def test_mechanical_fault_changes_response_without_a_process_interlock(self):
        plant = Equipment()
        plant.advance(1.0,[10000,10000],[True,True],[True,False])
        self.assertEqual(plant.positions[0],0.0)
        self.assertEqual(plant.positions[1],5.0)

    def test_restart_restores_physical_position_and_level(self):
        plant = Equipment(level_m=7.5,positions=[35.0,20.0])
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "equipment.json"
            plant.save(path)
            restored = Equipment.load(path)
        self.assertEqual(restored.level_m,7.5)
        self.assertEqual(restored.positions,[35.0,20.0])


if __name__ == "__main__":
    unittest.main()
