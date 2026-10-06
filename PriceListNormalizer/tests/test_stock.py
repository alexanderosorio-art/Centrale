import sys
import unittest
from pathlib import Path
from io import BytesIO
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stock_reader import procesar_stock, COLUMNAS_CRM
from common import excluir_cajas_abiertas
from exports import generar_tsv
from processing import procesar_archivos
from datetime import date


class StockTests(unittest.TestCase):
    def test_two_providers_no_invention(self):
        f = BytesIO()
        with pd.ExcelWriter(f, engine='openpyxl') as w:
            pd.DataFrame([['001', 'PN-A', 'Normal', 0], ['002', 'PN-A', 'BAD BOX normal', 1]],
                columns=['SKU', 'VDR_PARTNBR', 'DESCRIPCION', 'BOH']).to_excel(w, sheet_name='Ingram micro', index=False)
            pd.DataFrame([['Modelo', 'PN-A', 3], ['Modelo', 'PN-A', 2]],
                columns=['Modelo', 'Número de Parte', 'Canales']).to_excel(w, sheet_name='Compusoluciones', index=False)
        f.name = 'stock.xlsx'
        resumen, resultados = procesar_stock([f])
        self.assertTrue((resumen.Estado == 'Procesado').all())
        self.assertEqual(list(resultados['Ingram'].quantity), [0])
        self.assertEqual(list(resultados['Compusoluciones'].quantity), [3, 2])
        for proveedor, df in resultados.items():
            self.assertEqual(list(df.columns), COLUMNAS_CRM)
            for c in ['currency', 'currency_unaware_cost_neto', 'expiry_date', 'condition', 'working_days_to_deliver', 'brand']:
                self.assertTrue((df[c] == '').all())
            texto = generar_tsv(df)
            self.assertNotIn('provider_code', texto)
            self.assertEqual(len(texto.splitlines()[0].split('\t')), 10)
        self.assertTrue((resultados['Compusoluciones'].provider_code == '').all())

    def test_boxes_all_price_providers(self):
        f = BytesIO()
        with pd.ExcelWriter(f, engine='openpyxl') as w:
            pd.DataFrame([['A', 10, 2, 'open box producto'], ['B', 10, 3, 'bad-box producto'], ['C', 10, 4, 'Normal']],
                columns=['CODIGO', 'PRECIO', 'STOCK', 'DESCRIPCION']).to_excel(w, index=False)
        f.name = 'lista.xlsx'
        _, df = procesar_archivos([f], date(2026, 10, 6), 'Coimco')
        self.assertEqual(list(df.provider_code), ['C'])
        self.assertEqual(len(excluir_cajas_abiertas(pd.DataFrame({'name': ['OPENBOX', 'BAD_BOX', 'BOX normal']}))), 1)
