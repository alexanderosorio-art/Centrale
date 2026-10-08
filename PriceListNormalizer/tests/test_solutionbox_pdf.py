import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import BytesIO
from datetime import date
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from processing import procesar_archivos


class SolutionBoxPdfTests(unittest.TestCase):
    def test_pdf_merged_header(self):
        pagina = MagicMock()
        pagina.extract_tables.return_value = [[
            ['STOCK SKU DESCRIPCIÓN precio unitario', None, None, None],
            ['78', 'LBE-5AC-GEN2', 'Radio', '$ 60,38'],
            ['0', 'B', 'Sin stock', '$ 100,00'],
            ['1', 'C', 'BAD BOX Radio', '$ 10,00'],
            ['30 DIAS', 'D', 'Encargo', '$ 10,00']]]
        documento = MagicMock()
        documento.__enter__.return_value.pages = [pagina]
        f = BytesIO(b'fixture'); f.name = 'lista.pdf'
        with patch('pdfplumber.open', return_value=documento):
            resumen, df = procesar_archivos([f], date(2026, 10, 8), 'SolutionBox')
        self.assertEqual(resumen.iloc[0]['Estado'], 'Procesado')
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0].quantity, 78)
        self.assertEqual(df.iloc[0].currency_unaware_cost_neto, 60.38)
        self.assertEqual(df.iloc[0].mpn, '')
        self.assertEqual(df.iloc[0].brand, '')
