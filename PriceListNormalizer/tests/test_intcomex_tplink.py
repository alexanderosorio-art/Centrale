import sys
import unittest
from io import BytesIO
from pathlib import Path
from datetime import date
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from providers.intcomex import leer


class TpLinkTests(unittest.TestCase):
    def test_special_price_stock_and_explicit_brand(self):
        archivo = BytesIO()
        pd.DataFrame([
            ['TP-Link', 'NW1', 'PN1', 'Adaptador', 256, 7, 6.096848],
            ['TP-Link', 'NW2', 'PN2', 'Router', 2, 20, None],
            ['TP-Link', 'NW3', 'PN3', 'Sin stock', 0, 10, 8],
        ], columns=['Manuf Brand', 'Product ID', 'MPN', 'Product Name Trax', 'Stock', 'Precio Lista', 'Precio especial']).to_excel(archivo, index=False)
        archivo.name = 'TP-Link.xlsx'
        d, _, _ = leer(archivo, date(2026, 11, 30), 'USD')
        self.assertEqual(d.provider_code.tolist(), ['NW1', 'NW2'])
        self.assertEqual(d.currency_unaware_cost_neto.tolist(), [6.096848, 20])
        self.assertEqual(d.quantity.tolist(), [256, 2])
        self.assertTrue(d.brand.eq('TP-Link').all())
        self.assertEqual(d.mpn.tolist(), ['PN1', 'PN2'])

