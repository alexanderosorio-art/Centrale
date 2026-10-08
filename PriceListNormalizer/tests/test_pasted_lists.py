import sys
import unittest
from pathlib import Path
from datetime import date
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pasted_lists import interpretar_texto, archivo_mapeado, detectar_columnas, COLUMNAS
from processing import procesar_archivos


class PastedTests(unittest.TestCase):
    def test_detection_and_no_invention(self):
        for proveedor in ('Ingram', 'Intcomex', 'Coimco', 'Otro'):
            m, dudas = detectar_columnas(COLUMNAS, proveedor)
            self.assertFalse(dudas)
            self.assertEqual(m['provider_code'], 'MATERIAL/SKU')
            self.assertIsNone(m['brand'])
        m, dudas = detectar_columnas(['SKU', 'Stock', 'Precio', 'Precio Oferta'], 'Ingram')
        self.assertIn('currency_unaware_cost_neto', dudas)
        self.assertIsNone(m['currency_unaware_cost_neto'])
        m, dudas = detectar_columnas(['PN', 'Stock', 'Precio'], 'Kepler')
        self.assertFalse(dudas)
        self.assertEqual(m['provider_code'], 'PN')

    def test_provider_price_rules(self):
        m, dudas = detectar_columnas(['ID', 'Stock', 'Precio Neto detalle', 'Precio Neto x mayor'], 'Facciatech')
        self.assertFalse(dudas)
        self.assertEqual(m['currency_unaware_cost_neto'], 'Precio Neto detalle')
        m, dudas = detectar_columnas(['SKU', 'Stock', 'Precio Venta', 'Precio Volumen'], 'Tecnoglobal')
        self.assertFalse(dudas)
        self.assertEqual(m['currency_unaware_cost_neto'], 'Precio Volumen')
        _, dudas = detectar_columnas(['SKU', 'Stock', 'Precio PVP'], 'Otro')
        self.assertIn('currency_unaware_cost_neto', dudas)

    def test_auto_vertical(self):
        t = interpretar_texto('SKU\nPrecio\nStock\nABC\n12,5\n3')
        self.assertEqual(list(t.columns), ['SKU', 'Precio', 'Stock'])
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
