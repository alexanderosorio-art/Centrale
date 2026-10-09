import unittest
from datetime import date
import pandas as pd
from providers.kepler import procesar_kepler


class KeplerPNTests(unittest.TestCase):
    def test_confirmed_code_equivalence(self):
        df = pd.DataFrame({'CODIGO': ['CL-A-\nB'], 'VALOR': [23.6], 'STOCK': [9], 'DESCRIPCION': ['Cooler']})
        d = procesar_kepler(df, date(2026, 10, 23), 'PREVENTA TT.xlsx', 'USD')
        self.assertEqual(d.iloc[0].provider_code, 'CL-A-B')
        self.assertEqual(d.iloc[0].mpn, 'CL-A-B')
        self.assertEqual(d.iloc[0].brand, '')
        df['PN'] = ['PN-EXPLICITO']
        d = procesar_kepler(df, date(2026, 10, 23), 'PREVENTA TT.xlsx', 'USD')
        self.assertEqual(d.iloc[0].mpn, 'PN-EXPLICITO')
