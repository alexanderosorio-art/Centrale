"""Smoke test de Streamlit con cargas sintéticas, sin navegador ni credenciales."""
import sys
import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_providers import excel, PLANTILLAS


class AppTests(unittest.TestCase):
    def test_upload_process_and_reset(self):
        source = Path(__file__).resolve().parents[1] / 'app.py'
        wrapper = f'''import streamlit as st
from unittest.mock import patch
from pathlib import Path
with patch('streamlit.file_uploader', return_value=st.session_state.get('_files', [])):
    exec(compile(Path({str(source)!r}).read_text(encoding='utf-8'), {str(source)!r}, 'exec'))
'''
        app = AppTest.from_string(wrapper, default_timeout=20).run()
        self.assertFalse(app.exception)
        app.session_state['_files'] = [excel(PLANTILLAS['Intcomex'], [['A', 12.75, 3]], name='Intcomex.xlsx')]
        app.run()
        self.assertEqual(app.selectbox[0].value, 'Intcomex')
        self.assertEqual(app.selectbox[1].value, 'USD')
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.session_state['lote'][1]), 1)
        app.selectbox[1].select('CLP').run()
        self.assertNotIn('lote', app.session_state)
        app.button[0].click().run()
        self.assertEqual(app.session_state['lote'][1].iloc[0].currency, 'CLP')
        app.session_state['_files'] = [excel(PLANTILLAS['Ingram'], [['A', 12, 3]], name='Ingram.xlsx', second_sheet=True)]
        app.run()
        self.assertEqual(app.selectbox[0].value, 'Ingram')
        self.assertNotIn('lote', app.session_state)
        self.assertEqual(app.multiselect[0].value, [])
        app.multiselect[0].select('MATERIAL').select('OTRA').run()
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.session_state['lote'][1]), 2)


if __name__ == '__main__':
    unittest.main()
