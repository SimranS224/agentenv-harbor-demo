import unittest
from rescue_demo.world import episodes,grade,optimum
class WorldTests(unittest.TestCase):
 def test_events(self):
  e=episodes();self.assertIsNotNone(optimum(e[0]));self.assertIsNone(optimum(e[3]));self.assertEqual(optimum(e[0]),optimum(e[4]))
 def test_empty_is_only_safe_when_sealed(self):
  self.assertEqual([grade(e,[])['ok'] for e in episodes()],[False,False,False,True,False])
 def test_teleport_rejected(self):
  e=episodes()[0];self.assertFalse(grade(e,[e['start'],e['goal']])['ok'])
if __name__=='__main__':unittest.main()
