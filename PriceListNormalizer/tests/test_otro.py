import sys
import unittest
from io import BytesIO
from pathlib import Path
from datetime import date
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from providers.otro import leer


class OtroTests(unittest.TestCase):
    def test_remate_price_and_missing_fields(self):
        archivo = BytesIO()
        pd.DataFrame([
            ['KUKST01WB', 'UPS KAISE', 151.24, 'USD 127', 6],
            ['KUET01WB', 'UPS', 138.65, None, 75],
            ['KUET06WB', 'Próxima llegada', 578.5, None, 0],
        ], columns=['CODIGO PROVEEDOR', 'DESCRIPCION', 'Valor', 'Valor especial por remate de unidades', 'Stock']).to_excel(archivo, index=False)
        archivo.name = 'lista.xlsx'
        d, _, _ = leer(archivo, date(2026, 11, 30), 'USD')
        self.assertEqual(d.provider_code.tolist(), ['KUKST01WB', 'KUET01WB'])
        self.assertEqual(d.currency_unaware_cost_neto.tolist(), [127, 138.65])
        self.assertTrue(d.mpn.eq('').all())
        self.assertTrue(d.brand.eq('').all())

