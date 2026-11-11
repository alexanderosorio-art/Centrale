import sys
import unittest
from io import BytesIO
from pathlib import Path
from datetime import date
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from providers.ingram import leer


class IngramMsiTests(unittest.TestCase):
    def test_total_stock_and_localized_price(self):
        archivo = BytesIO()
        pd.DataFrame([
            ['6840159', '912-V531-682', 'Producto MSI', 'Tarjeta Gráfica', 2, '$1.221,05'],
            ['6632642', '912-V538-008', 'Sin stock', 'Tarjeta Gráfica', 0, '$430,56'],
        ], columns=['MATERIAL/SKU', 'PART_NUMBER', 'MKT NAME', 'TIPO DE PRODUCTO', 'STOCK TOTAL', 'PRECIO']).to_excel(archivo, index=False)
        archivo.name = 'MSI.xlsx'
        d, _, _ = leer(archivo, date(2026, 11, 25), 'USD')
        self.assertEqual(len(d), 1)
        self.assertEqual(d.iloc[0].currency_unaware_cost_neto, 1221.05)
        self.assertEqual(d.iloc[0].quantity, 2)
        self.assertEqual(d.iloc[0].mpn, '912-V531-682')
        self.assertEqual(d.iloc[0]['name'], 'Producto MSI')
        self.assertEqual(d.iloc[0].brand, '')

