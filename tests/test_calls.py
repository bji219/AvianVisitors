import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "avian" / "scripts"))
import check_calls  # noqa: E402


class CallsFile(unittest.TestCase):
    def test_every_entry_is_sourced_and_well_formed(self):
        data = json.loads(check_calls.CALLS.read_text(encoding="utf-8"))
        self.assertGreater(len(data), 50)
        self.assertEqual(check_calls.problems(data), [])

    def test_bad_entries_are_caught(self):
        bad = {"not binomial": {"common": "X", "mnemonics": [""], "source": "S",
                                "url": "https://example.com/x"}}
        self.assertEqual(len(check_calls.problems(bad)), 3)


if __name__ == "__main__":
    unittest.main()
