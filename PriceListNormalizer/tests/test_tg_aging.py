import sys
import unittest
from io import BytesIO
from pathlib import Path
from datetime import date
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from providers.tecnoglobal import leer


class AgingTests(unittest.TestCase):
    def test_aging_price_and_quantity_stay_paired(self):
        archivo = BytesIO()
        with pd.ExcelWriter(archivo, engine='openpyxl') as writer:
            pd.DataFrame([
                ['TG1', 'PN1', 'Con aging parcial', 100, 120, 5, 90],
                ['TG2', 'PN2', 'Sin aging', 10, 80, None, None],
                ['TG3', 'PN3', 'Aging sin precio', 8, 50, 2, None],
                ['TG4', 'PN4', 'Aging sin cantidad', 7, 60, 0, 40],
            ], columns=['SKU', 'PartNumber', 'Descripción', 'Stock', 'VALOR', 'AGING', 'VALOR AGING']).to_excel(writer, sheet_name='Toner&Tintas', index=False)
            pd.DataFrame([['TG5', 'PN5', 'Plotter', 4, 70]], columns=[
                'SKU', 'PartNumber', 'Descripción', 'Stock', 'VALOR USD']).to_excel(writer, sheet_name='Sum_Plotter', index=False)
        archivo.name = 'HP.xlsx'
        d, _, detalle = leer(archivo, date(2026, 11, 30), 'USD')
        self.assertEqual(d.provider_code.tolist(), ['TG1', 'TG2', 'TG3', 'TG4', 'TG5'])
        self.assertEqual(d.quantity.tolist(), [5, 10, 8, 7, 4])
        self.assertEqual(d.currency_unaware_cost_neto.tolist(), [90, 80, 50, 60, 70])
        self.assertTrue(d.brand.eq('').all())
        self.assertIn('Sum_Plotter', detalle)

