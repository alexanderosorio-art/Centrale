import sys
import unittest
from io import BytesIO
from pathlib import Path
from datetime import date
from unittest.mock import patch
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from providers.intcomex import leer


class HpeBlocksTests(unittest.TestCase):
    def test_missing_codes_two_blocks_and_transit(self):
        archivo = BytesIO()
        filas = [
            ['FORMATO', 'Part Number', 'DESCRIPCIÓN', 'PRECIO UN VENTA', 'Precio PROMO Referencial', 'TIEMPO DE ENTREGA', None],
            ['Servidor', 'PN1', 'Servidor HPE', 12000, 9450, '2 unidades Entrega Inmediata', None],
            ['Servidor', 'PN2', 'En tránsito', 12000, 9000, '4 unidades en tránsito', None],
            ['FORMATO', 'PN', 'DESCRIPCIÓN', 'QTY', 'PRECIO UN VENTA', 'Precio PROMO USD', 'TIEMPO DE ENTREGA'],
            ['Disco', 'PN3', 'Disco HPE', 1, 770, 470, '15 unidades entrega inmediata'],
        ]
        with pd.ExcelWriter(archivo, engine='openpyxl') as writer:
            pd.DataFrame(filas).to_excel(writer, sheet_name='LP GEN12', header=False, index=False)
        archivo.name = 'HPE.xlsx'
        def resolver(tabla, proveedor):
            self.assertNotIn('PN2', tabla.mpn.tolist())
            tabla['provider_code'] = tabla.mpn.map({'PN1': 'IX1', 'PN3': 'IX3'})
            return tabla, [], ''
        with patch('providers.intcomex.resolver_por_catalogo', side_effect=resolver):
            d, _, _ = leer(archivo, date(2026, 11, 30), 'USD')
        self.assertEqual(d.provider_code.tolist(), ['IX1', 'IX3'])
        self.assertEqual(d.quantity.tolist(), [2, 15])
        self.assertEqual(d.currency_unaware_cost_neto.tolist(), [9450, 470])

