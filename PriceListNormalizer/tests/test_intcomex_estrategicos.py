import unittest
from datetime import date
from test_providers import excel
from processing import procesar_archivos


class EstrategicosTests(unittest.TestCase):
    def test_special_price_pn_and_expired_date(self):
        f = excel(['Product ID', 'MPN', 'Product Name', 'Marca', 'Stock',
                   'Precio especial neto unit. Clientes Estratégicos'],
                  [['MT021XIA97', 48341, 'Monitor', 'Xiaomi', 339, 53.9]],
                  name='Xiaomi hasta 09 Octubre 2026.xlsx')
        s, d = procesar_archivos([f], date(2026, 10, 27), 'Intcomex', 'USD')
        self.assertEqual(s.iloc[0]['Estado'], 'Procesado')
        self.assertEqual(d.iloc[0].provider_code, 'MT021XIA97')
        self.assertEqual(d.iloc[0].mpn, '48341')
        self.assertEqual(d.iloc[0].currency_unaware_cost_neto, 53.9)
        self.assertEqual(d.iloc[0].expiry_date, '09-10-2026  12:00')
        self.assertEqual(d.iloc[0].brand, 'Xiaomi')
