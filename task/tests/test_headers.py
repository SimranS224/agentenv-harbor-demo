import unittest
import requests
from requests.structures import CaseInsensitiveDict


class Headers(unittest.TestCase):
    def test_uses_checkout(self):
        self.assertTrue(requests.__file__.startswith('/app/src/requests/'))

    def test_case_insensitive_lookup(self):
        h = CaseInsensitiveDict({'Content-Type': 'application/json'})
        for key in ['Content-Type', 'content-type', 'CONTENT-TYPE', 'cOnTeNt-TyPe']:
            self.assertEqual(h[key], 'application/json')

    def test_update_and_casing(self):
        h = CaseInsensitiveDict({'Accept': 'text/plain'})
        h['aCCEPT'] = 'application/json'
        self.assertEqual(len(h), 1)
        self.assertEqual(list(h), ['aCCEPT'])
        self.assertEqual(h['ACCEPT'], 'application/json')

    def test_delete(self):
        h = CaseInsensitiveDict({'Accept': '*/*'})
        del h['ACCEPT']
        self.assertEqual(len(h), 0)

    def test_copy_equality_and_missing(self):
        h = CaseInsensitiveDict({'X-Token': 'test'})
        self.assertEqual(h, {'x-token': 'test'})
        self.assertEqual(h.copy()['X-TOKEN'], 'test')
        with self.assertRaises(KeyError):
            h['missing']

    def test_real_prepared_request(self):
        p = requests.Request('GET', 'https://example.invalid',
                             headers={'X-Demo': 'hello'}).prepare()
        self.assertEqual(p.headers['X-DEMO'], 'hello')


if __name__ == '__main__':
    unittest.main(verbosity=2)
