import unittest
from datetime import date
from io import BytesIO
import pandas as pd
from test_providers import excel
from processing import procesar_archivos


class TGPromosTests(unittest.TestCase):
    def test_linksys_special_price(self):
        f = excel(['Marca', 'S.K.U.', 'PartNumber', 'Descripción', 'Precio Especial', 'Stock Disponible'],
                  [['LINKSYS', 'LKR-009', 'LN1602', 'Router', 'USD$ 224,72', 9]])
        s, d = procesar_archivos([f], date(2026, 10, 22), 'Tecnoglobal', 'CLP')
        self.assertEqual(s.iloc[0]['Estado'], 'Procesado')
        self.assertEqual(d.iloc[0].currency, 'USD')
        self.assertEqual(d.iloc[0].currency_unaware_cost_neto, 224.72)
        self.assertEqual(d.iloc[0].mpn, 'LN1602')

    def test_cyber_currency_date_and_missing_brand(self):
        f = BytesIO()
        rows = [['Precios netos en pesos , Vigencias hasta el 09-10-2026'],
                ['Cod. TG', 'PartNumber', 'Descripción', 'Stock', 'Precio Venta', 'Cyber'],
                ['A', 'PN-A', 'Producto', 3, 120, 90],
                ['B', 'PN-B', 'BAD BOX Producto', 2, 120, 90],
                ['C', 'PN-C', 'Sin stock', 0, 120, 90]]
        with pd.ExcelWriter(f, engine='openpyxl') as writer:
            pd.DataFrame([['CODIGO TG', 'PN'], ['A', 'PN-A']]).to_excel(writer, sheet_name='Hoja1', index=False, header=False)
            pd.DataFrame(rows).to_excel(writer, sheet_name='Hoja2', index=False, header=False)
        f.name = 'TG Cyber.xlsx'
        s, d = procesar_archivos([f], date(2026, 10, 22), 'Tecnoglobal', 'USD')
        self.assertEqual(s.iloc[0]['Estado'], 'Procesado')
        self.assertEqual(len(d), 1)
        self.assertEqual(d.iloc[0].currency, 'CLP')
        self.assertEqual(d.iloc[0].currency_unaware_cost_neto, 90)
        self.assertEqual(d.iloc[0].expiry_date, '09-10-2026  12:00')
        self.assertEqual(d.iloc[0].brand, '')
