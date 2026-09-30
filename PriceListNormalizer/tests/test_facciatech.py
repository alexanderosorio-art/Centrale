"""Precios de detalle y aislamiento de Resumen, con datos sintéticos."""
import unittest
from io import BytesIO
import pandas as pd
from test_providers import FECHA
from processing import procesar_archivos


def archivo(rows, header=None, summary=True):
    header = header or ['ID', 'Part Number', 'Nombre', 'Marca', 'Stock',
                        'Precio Neto  detalle', 'Precio Neto x mayor']
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        pd.DataFrame([['Titulo'] + [None] * (len(header)-1), header, *rows]).to_excel(
            writer, index=False, header=False, sheet_name=' Resumen ' if summary else 'Catalogo')
        pd.DataFrame([header, ['UNWANTED', 'PN-OTHER', 'Otro', 'Marca', 100, 1, 0.5]]).to_excel(
            writer, index=False, header=False, sheet_name='Otra')
    buffer.name = 'Facciatech.xlsx'
    buffer.seek(0)
    return buffer


class FacciatechTests(unittest.TestCase):
    def test_detail_price_even_if_wholesale_is_lower(self):
        rows = [[20871, 'PN-A', 'Producto', 'Marca', 969, 4100, 3500],
                ['0002', None, 'Segundo', None, 1, 5000, 1000]]
        summary, result = procesar_archivos([archivo(rows)], FECHA, 'Facciatech')
        self.assertEqual(summary.iloc[0]['Estado'], 'Procesado')
        self.assertEqual(list(result.provider_code), ['20871', '0002'])
        self.assertEqual(list(result.currency_unaware_cost_neto), [4100, 5000])
        self.assertEqual(list(result.mpn), ['PN-A', ''])
        self.assertEqual(list(result.brand), ['Marca', ''])
        self.assertEqual(set(result.currency), {'CLP'})

    def test_filters_and_never_falls_back_to_wholesale(self):
        rows = [['A', 'PN-A', 'Producto', 'Marca', 0, 4100, 3500],
                ['B', 'PN-B', 'Producto', 'Marca', 2, None, 3500],
                ['C', 'PN-C', 'Producto', 'Marca', '30 dias', 4100, 3500],
                [None, 'PN-D', 'Producto', 'Marca', 2, 4100, 3500],
                ['E', 'PN-E', 'Producto', 'Marca', 2, '$4.100.-', 3500]]
        _, result = procesar_archivos([archivo(rows)], FECHA, 'Facciatech')
        self.assertEqual(list(result.provider_code), ['E'])
        self.assertEqual(result.iloc[0].currency_unaware_cost_neto, 4100)

    def test_required_sheet_and_detail_column(self):
        for buffer in [archivo([], summary=False), archivo([], header=[
                'ID', 'Part Number', 'Nombre', 'Marca', 'Stock', 'Precio Neto x mayor'])]:
            summary, result = procesar_archivos([buffer], FECHA, 'Facciatech')
            self.assertEqual(summary.iloc[0]['Estado'], 'Error')
            self.assertTrue(result.empty)


if __name__ == '__main__':
    unittest.main()
