import sys
import unittest
from io import BytesIO
from pathlib import Path
from datetime import date
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from providers.tecnoglobal import leer


class LenovoTgTests(unittest.TestCase):
    def test_current_stock_price_not_arrival_or_warranty(self):
        archivo = BytesIO()
        pd.DataFrame([
            ['LNS-608', '13FA0032CS', 'Equipo', 'En stock ', 3, 700, 'Oferta US$811,77'],
            ['LNS-609', 'PN2', 'Futuro', 'En tránsito', 20, 600, 900],
            [None, '5WS1P43542', 'Garantía', 'Stock Unico', 1, None, 20.83],
        ], columns=['Código', 'Part Number', 'Descripción', 'Estado', 'Cantidad', 'Precio Próxima Llegada', 'Precio Stock USD']).to_excel(archivo, index=False)
        archivo.name = 'Lenovo TG.xlsx'
        d, _, _ = leer(archivo, date(2026, 11, 30), 'USD')
        self.assertEqual(d.provider_code.tolist(), ['LNS-608'])
        self.assertEqual(d.currency_unaware_cost_neto.tolist(), [811.77])
        self.assertEqual(d.quantity.tolist(), [3])
        self.assertEqual(d.mpn.tolist(), ['13FA0032CS'])
        self.assertTrue(d.brand.eq('').all())

