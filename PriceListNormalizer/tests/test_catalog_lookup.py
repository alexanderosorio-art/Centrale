import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from catalog_lookup import resolver_por_catalogo
from pasted_lists import archivo_mapeado
from pasted_lists import detectar_columnas


class CatalogLookupTests(unittest.TestCase):
    def test_intcomex_can_use_name_as_catalog_lookup_key(self):
        mapping, doubts = detectar_columnas(['MKT NAME', 'STOCK', 'PRECIO'], 'Intcomex')
        self.assertIsNone(mapping['provider_code'])
        self.assertNotIn('provider_code', doubts)

    def test_ingram_can_use_pn_as_catalog_lookup_key(self):
        mapping, doubts = detectar_columnas(['PN', 'QTY', 'PRECIO'], 'Ingram')
        self.assertIsNone(mapping['provider_code'])
        self.assertNotIn('provider_code', doubts)

        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'Ingram.csv')
            pd.DataFrame([{'provider': 'INGRAM MICRO', 'provider_code': '6327493', 'mpn': 'PRIME A620M-K'}]).to_csv(path, index=False)
            old = os.environ.get('PRICE_LIST_CATALOG_DIR')
            os.environ['PRICE_LIST_CATALOG_DIR'] = folder
            try:
                tabla = pd.DataFrame([{'provider_code': '', 'mpn': 'PRIME A620M-K', 'name': ''}])
                result, pending, _ = resolver_por_catalogo(tabla, 'Ingram')
                self.assertFalse(pending)
                self.assertEqual(result.loc[0, 'provider_code'], '6327493')
            finally:
                if old is None:
                    os.environ.pop('PRICE_LIST_CATALOG_DIR', None)
                else:
                    os.environ['PRICE_LIST_CATALOG_DIR'] = old

    def test_intcomex_unique_and_ambiguous(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'Intcomex.csv')
            pd.DataFrame([
                {'provider_code': 'MB-1', 'mpn': 'PRIME B760M-K D4', '_name': 'ASUS B760'},
                {'provider_code': 'X-1', 'mpn': 'PRIME X870-P WIFI', '_name': 'ASUS X870'},
                {'provider_code': 'X-2', 'mpn': 'PRIME X870-P WIFI', '_name': 'ASUS X870'},
            ]).to_csv(path, index=False)
            old = os.environ.get('PRICE_LIST_CATALOG_DIR')
            os.environ['PRICE_LIST_CATALOG_DIR'] = folder
            try:
                tabla = pd.DataFrame([
                    {'provider_code': '', 'currency_unaware_cost_neto': '82,11', 'quantity': '100',
                     'mpn': '', 'name': 'PRIME B760M-K D4', 'brand': 'ASUS'},
                    {'provider_code': '', 'currency_unaware_cost_neto': '226,84', 'quantity': '58',
                     'mpn': '', 'name': 'PRIME X870-P WIFI', 'brand': 'ASUS'},
                ])
                result, pending, detail = resolver_por_catalogo(tabla, 'Intcomex')
                self.assertEqual(result.loc[0, 'provider_code'], 'MB-1')
                self.assertEqual(pending, [1])
                self.assertIn('varios códigos', detail)
            finally:
                if old is None:
                    os.environ.pop('PRICE_LIST_CATALOG_DIR', None)
                else:
                    os.environ['PRICE_LIST_CATALOG_DIR'] = old

    def test_bundled_catalog_is_used_without_upload(self):
        with tempfile.TemporaryDirectory() as folder:
            catalog_dir = Path(folder) / 'Ingram'
            catalog_dir.mkdir()
            pd.DataFrame([
                {'provider': 'INGRAM MICRO', 'provider_code': '6327493',
                 'mpn': 'PRIME A620M-K', '_name': 'ASUS PRIME A620M-K'},
            ]).to_csv(catalog_dir / '001.csv', index=False)
            old = os.environ.pop('PRICE_LIST_CATALOG_DIR', None)
            try:
                with patch('catalog_lookup.BUNDLED_CATALOG_DIR', Path(folder)):
                    tabla = pd.DataFrame([{'provider_code': '', 'mpn': 'PRIME A620M-K', 'name': ''}])
                    result, pending, _ = resolver_por_catalogo(tabla, 'Ingram')
                self.assertFalse(pending)
                self.assertEqual(result.loc[0, 'provider_code'], '6327493')
            finally:
                if old is not None:
                    os.environ['PRICE_LIST_CATALOG_DIR'] = old

    def test_missing_price_is_dropped_for_pasted_rows(self):
        df = pd.DataFrame([
            {'name': 'Producto válido', 'provider_code': '', 'currency_unaware_cost_neto': '10,5', 'quantity': '2', 'mpn': '', 'brand': ''},
            {'name': 'Sin precio', 'provider_code': '', 'currency_unaware_cost_neto': '', 'quantity': '3', 'mpn': '', 'brand': ''},
        ])
        archivo = archivo_mapeado(df, {k: k for k in df.columns}, permitir_codigo_ausente=True)
        self.assertEqual(len(archivo.tabla_pegada), 1)
        self.assertEqual(archivo.filas_sin_precio, 1)


if __name__ == '__main__':
    unittest.main()

