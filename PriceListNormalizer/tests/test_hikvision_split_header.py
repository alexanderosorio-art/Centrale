import sys
import unittest
from io import BytesIO
from pathlib import Path
from datetime import date
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from providers.intcomex import leer


class HikvisionHeaderTests(unittest.TestCase):
    def test_two_row_header_and_stock_plus(self):
        archivo = BytesIO()
        pd.DataFrame([
            ['Imagen', 'SKU', 'PART #', 'Descripción', 'DPV', None],
            ['Cámaras', None, None, None, 'DPV', 'Precio Neto USD'],
            [None, 'ES213HIK97', 'PN-1', 'Cámara', '500+', 9.5],
            ['Otra categoría', None, None, None, 'DPV', None],
            [None, 'ES213HIK96', 'PN-2', 'Cámara 2', '0', 10.2],
        ]).to_excel(archivo, index=False, header=False)
        archivo.name = 'HIK.xlsx'
        d, _, _ = leer(archivo, date(2026, 11, 27), 'USD')
        self.assertEqual(d.provider_code.tolist(), ['ES213HIK97'])
        self.assertEqual(d.quantity.tolist(), [500])
        self.assertEqual(d.currency_unaware_cost_neto.tolist(), [9.5])
        self.assertEqual(d.mpn.tolist(), ['PN-1'])

