import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from file_readers import sugerir_hojas


class SheetSuggestionsTests(unittest.TestCase):
    def test_mixed_suppliers(self):
        hojas = ['ADATA INGRAM', 'XPG TG', 'ADATA TG']
        self.assertEqual(sugerir_hojas(hojas, 'Ingram'), hojas[:1])
        self.assertEqual(sugerir_hojas(hojas, 'Tecnoglobal'), hojas[1:])
        self.assertEqual(sugerir_hojas(hojas, 'Intcomex'), [])

    def test_unlabelled_sheets_remain_available(self):
        hojas = ['NOTEBOOK', 'CONSUMO', 'DESKTOP']
        self.assertEqual(sugerir_hojas(hojas, 'Ingram'), hojas)

