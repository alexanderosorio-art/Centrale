import sys
import unittest
from pathlib import Path
from io import BytesIO
from datetime import date
from unittest.mock import MagicMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from intcomex_nexxt_pdf import leer_nexxt_pdf, ENCABEZADOS


class NexxtPdfTests(unittest.TestCase):
    def test_continuation_page_price_spaces_and_transit(self):
        pagina1, pagina2 = MagicMock(), MagicMock()
        pagina1.extract_text.return_value = 'Validez30-11-2026'
        pagina2.extract_text.return_value = ''
        pagina1.extract_tables.return_value = [[ENCABEZADOS,
            ['', 'PN1', 'AW222NXT61', 'Producto', '4', '500', '$ 1 2,94'],
            ['', 'PN2', 'AW222NXT62', 'Sin stock', 'Sin stock', '100', '$ 8,56']]]
        pagina2.extract_tables.return_value = [[
            ['', 'PN3', 'AW222NXT63', 'Página dos', 'Más de 100 unidades', '300', '$ 1 00,10']]]
        with patch('pdfplumber.open') as abrir:
            abrir.return_value.__enter__.return_value.pages = [pagina1, pagina2]
            d, leidos, _ = leer_nexxt_pdf(BytesIO(), date(2026, 12, 1))
        self.assertEqual(leidos, 3)
        self.assertEqual(d.provider_code.tolist(), ['AW222NXT61', 'AW222NXT63'])
        self.assertEqual(d.quantity.tolist(), [4, 100])
        self.assertEqual(d.currency_unaware_cost_neto.tolist(), [12.94, 100.1])
        self.assertTrue(d.expiry_date.eq('30-11-2026  12:00').all())
        self.assertTrue(d.brand.eq('').all())

