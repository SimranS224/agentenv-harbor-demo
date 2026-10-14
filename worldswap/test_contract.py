import unittest
from lander_demo.verify import verify
class Contract(unittest.TestCase):
 def test_hard_landing_fails_even_at_pad(self):
  self.assertFalse(verify({'pad_x':100},{'contact':{'x':100,'vx':0,'vy':-30,'t':10}})['passed'])
 def test_wrong_pad_fails_even_if_slow(self):
  self.assertFalse(verify({'pad_x':100},{'contact':{'x':130,'vx':0,'vy':-1,'t':10}})['passed'])
 def test_hovering_is_not_landing(self):
  self.assertFalse(verify({'pad_x':100},{'contact':None,'final':{'x':100}})['passed'])
 def test_safe_touchdown(self):
  self.assertTrue(verify({'pad_x':100},{'contact':{'x':102,'vx':1,'vy':-3,'t':10}})['passed'])
if __name__=='__main__':unittest.main()
