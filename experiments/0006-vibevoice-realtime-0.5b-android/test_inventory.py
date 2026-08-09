import unittest

import check_inventory


class InventoryTest(unittest.TestCase):
    def test_structure(self):
        data, schema = check_inventory.load()
        check_inventory.check_structure(data, schema)

    def test_preview_dependency_is_protocol_v2(self):
        data, _ = check_inventory.load()
        check_inventory.check_preview_dependency(data)

    def test_arithmetic(self):
        data, _ = check_inventory.load()
        check_inventory.check_arithmetic(data)

    def test_runtime_evidence_contract(self):
        data, _ = check_inventory.load()
        check_inventory.check_recommendations(data)


if __name__ == "__main__":
    unittest.main()
