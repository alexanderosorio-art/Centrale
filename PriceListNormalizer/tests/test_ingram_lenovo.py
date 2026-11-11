import sys
import unittest
from pathlib import Path
from io import BytesIO
from datetime import date
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from providers.ingram import leer


class LenovoTests(unittest.TestCase):
    def test_selected_sheets_offer_currency_and_warranty(self):
        archivo = BytesIO()
        with pd.ExcelWriter(archivo, engine='openpyxl') as writer:
            pd.DataFrame([
                ['PN1', 1234567, 'Notebook', 1150, 910, 5, 25],
                ['PN2', 1234568, 'Desktop', 800, None, 2, 10],
                ['PN3', 1234569, 'Sin stock', 800, 700, 0, 10],
            ], columns=['PART NUMBER', 'SKU', 'DESCRIPCION', 'PRECIO NORMAL', 'PRECIO OFERTA', 'STOCK', '3Y Onsite']).to_excel(writer, sheet_name='NOTEBOOK', index=False)
            pd.DataFrame([['PN4', 7654321, 'Consumo', 600000, 500000, 3]], columns=[
                'Manufacturer Part Nu', 'Material', 'Material Description', 'PRECIO NORMAL CLP', 'PRECIO OFERTA CLP', 'STOCK'
            ]).to_excel(writer, sheet_name='CONSUMO', index=False)
            pd.DataFrame([['garantias']]).to_excel(writer, sheet_name='GARANTIAS', index=False)
        archivo.name = 'Lenovo.xlsx'
        archivo.seek(0)
        resultado, _, _ = leer(archivo, date(2026, 11, 25), 'USD', hojas_seleccionadas=['NOTEBOOK', 'CONSUMO'])
        self.assertEqual(resultado.provider_code.tolist(), ['1234567', '1234568', '7654321'])
        self.assertEqual(resultado.currency_unaware_cost_neto.tolist(), [910, 800, 500000])
        self.assertEqual(resultado.currency.tolist(), ['USD', 'USD', 'CLP'])
        self.assertEqual(resultado.mpn.tolist(), ['PN1', 'PN2', 'PN4'])
        self.assertTrue(resultado.brand.eq('').all())
        self.assertEqual(resultado.attrs['currency_policy'], 'SOURCE')

