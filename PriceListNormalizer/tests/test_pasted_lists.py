import sys
import unittest
from pathlib import Path
from datetime import date
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pasted_lists import interpretar_texto, archivo_mapeado, COLUMNAS
from processing import procesar_archivos


class PastedTests(unittest.TestCase):
    def test_vertical_markdown_all_providers(self):
        texto = '\n'.join(['**' + c + '**\n|   |\n| - |' for c in COLUMNAS] +
            ['6880410', '912-V812-231', 'MSI GAMER', '472924', 'GEFORCE GT 1030', '85', '$\u00a0 109,67'])
        tabla = interpretar_texto(texto)
        m = dict(provider_code='MATERIAL/SKU', mpn='PART_NUMBER', name='MKT NAME',
                 currency_unaware_cost_neto='PRECIO', quantity='STOCK DISPONIBLE', brand=None)
        for proveedor in ('Ingram', 'Intcomex', 'Tecnoglobal', 'Gerona', 'Otro'):
            s, d = procesar_archivos([archivo_mapeado(tabla, m)], date(2026, 10, 8), proveedor)
            self.assertEqual(s.iloc[0]['Estado'], 'Procesado')
            self.assertEqual(d.iloc[0].provider_code, '6880410')
            self.assertEqual(d.iloc[0].currency_unaware_cost_neto, 109.67)
            self.assertEqual(d.iloc[0].quantity, 85)
            self.assertEqual(d.iloc[0].brand, '')

    def test_tabular_and_incomplete(self):
        tabla = interpretar_texto('SKU\tPN\tPrecio\tStock\nA\tPN-A\t12,5\t3')
        self.assertEqual(tabla.iloc[0]['SKU'], 'A')
        with self.assertRaises(ValueError):
            interpretar_texto('SKU\tPrecio\tStock\nA\t12')
        with self.assertRaises(ValueError):
            interpretar_texto('\n'.join(COLUMNAS + ['A', 'PN']))
        with self.assertRaises(ValueError):
            archivo_mapeado(tabla, {'provider_code': 'SKU', 'currency_unaware_cost_neto': 'Precio', 'quantity': 'PN'})

    def test_markdown_table(self):
        tabla = interpretar_texto('| SKU | Precio | Stock |\n| --- | --- | --- |\n| A | 12,5 | 3 |')
        self.assertEqual(list(tabla.columns), ['SKU', 'Precio', 'Stock'])
