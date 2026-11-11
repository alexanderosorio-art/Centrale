import sys
import unittest
from io import BytesIO
from pathlib import Path
from datetime import date
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from providers.ingram import leer


class IngramWebTests(unittest.TestCase):
    def test_free_stock_unit_offer_and_expiry(self):
        archivo = BytesIO()
        pd.DataFrame([
            [5862260, 'PN1', 'Producto', 56, 12, 76.06, 68, 60, '13.11.2026'],
            [6119460, 'PN2', 'Reservado', 186, 0, 88.18, 79, 70, '13.11.2026'],
            [6119461, 'PN3', 'Sin oferta', 1, 1, 90, None, 50, '13.11.2026'],
        ], columns=['SKU IM', 'Modelo', 'Material Description', 'Inv Total', 'Inv Libre',
                    'Precio Normal USD', 'Oferta WEB Desde 1 unid.', 'Super WEB Desde 10 unid.', 'Vigenvia']).to_excel(archivo, index=False, sheet_name='ADATA INGRAM')
        archivo.name = 'Noviembre.xlsx'
        resultado, _, _ = leer(archivo, date(2026, 11, 25), 'CLP', hojas_seleccionadas=['ADATA INGRAM'])
        self.assertEqual(resultado.provider_code.tolist(), ['5862260', '6119461'])
        self.assertEqual(resultado.quantity.tolist(), [12, 1])
        self.assertEqual(resultado.currency_unaware_cost_neto.tolist(), [68, 90])
        self.assertTrue(resultado.expiry_date.eq('13-11-2026  12:00').all())
        self.assertEqual(resultado.attrs['currency_policy'], 'USD_ONLY')

