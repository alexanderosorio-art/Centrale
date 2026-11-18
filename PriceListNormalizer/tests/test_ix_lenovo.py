import sys
import unittest
from io import BytesIO
from pathlib import Path
from datetime import date
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from providers.intcomex import leer


class IxLenovoTests(unittest.TestCase):
    def test_equipment_accessories_and_transit(self):
        archivo = BytesIO()
        with pd.ExcelWriter(archivo, engine='openpyxl') as writer:
            pd.DataFrame([
                ['IX1', 'PN1', 'Notebook', 1000, 900, 3, 'Garantía USD$ 20'],
                ['IX2', 'PN2', 'Sin oferta', 800, None, 2, 'USD$ 10'],
                ['IX3', 'PN3', 'Futuro', 700, 600, '45 unidades en transito', ''],
            ], columns=['SKU', 'P/N', 'DESCRIPCION', 'PRECIO NORMAL USD$', 'PRECIO OFERTA USD$', 'STOCK', 'EXTENSION DE GARANTIA SUGERIDA']).to_excel(writer, sheet_name='LISTA DE PRECIOS', index=False)
            pd.DataFrame([
                ['IX4', 'PN4', 'Mochila', 10.48, 170],
                ['IX5', 'PN5', 'Cargador', 25, '400 unidades en transito'],
            ], columns=['SKU', 'P/N', 'DESCRIPCION', 'USD$ SIN IVA', 'STOCK']).to_excel(writer, sheet_name='ACCESORIOS', index=False)
            pd.DataFrame([['Contacto']]).to_excel(writer, sheet_name='CONTACTO', index=False)
        archivo.name = 'LENOVO IX.xlsx'
        d, _, _ = leer(archivo, date(2026, 11, 30), 'USD')
        self.assertEqual(d.provider_code.tolist(), ['IX1', 'IX2', 'IX4'])
        self.assertEqual(d.currency_unaware_cost_neto.tolist(), [900, 800, 10.48])
        self.assertEqual(d.quantity.tolist(), [3, 2, 170])
        archivo.seek(0)
        d, _, _ = leer(archivo, date(2026, 11, 30), 'USD', hojas_seleccionadas=['ACCESORIOS'])
        self.assertEqual(d.provider_code.tolist(), ['IX4'])

