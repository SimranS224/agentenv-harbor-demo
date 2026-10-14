import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from harbor_bridge.runner import manifest, task_hash, reward


class Contracts(unittest.TestCase):
    def test_reward_contract(self):
        self.assertEqual(reward('0\n'), 0)
        self.assertEqual(reward('1\n'), 1)
        for text in ['', 'NaN', '2', 'passed']:
            with self.assertRaises(ValueError):
                reward(text)

    def test_identity_detects_change(self):
        with TemporaryDirectory() as d:
            p = Path(d) / 'instruction.md'
            p.write_text('original')
            before = task_hash(manifest(Path(d)))
            self.assertEqual(before, task_hash(manifest(Path(d))))
            p.write_text('changed')
            self.assertNotEqual(before, task_hash(manifest(Path(d))))


if __name__ == '__main__':
    unittest.main()
