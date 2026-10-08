"""Smoke test de Streamlit con cargas sintéticas, sin navegador ni credenciales."""
import sys
import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_providers import excel, PLANTILLAS


class AppTests(unittest.TestCase):
    def test_stock_mode_name(self):
        source = Path(__file__).resolve().parents[1] / 'app.py'
        app = AppTest.from_file(str(source), default_timeout=20).run()
        self.assertEqual(app.expander[0].label, 'Lista')
        app.selectbox(key='tipo_procesamiento').select('Lista de stock').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.file_uploader[0].key, 'stock_archivos')

    def test_contextual_help_and_short_interface(self):
        source = Path(__file__).resolve().parents[1] / 'app.py'
        app = AppTest.from_file(str(source), default_timeout=20).run()
        self.assertFalse(app.exception)
        self.assertIn('PDF', app.file_uploader[0].proto.help)
        self.assertFalse(any('Puedes seleccionar varios archivos.' in c.value for c in app.caption))
        app.selectbox(key='proveedor_lista').select('Facciatech').run()
        self.assertIn('Precio Neto detalle', app.selectbox(key='proveedor_lista').proto.help)
        self.assertEqual(app.button(key='procesar_listas').proto.type, 'primary')

    def test_clear_pasted_list(self):
        source = Path(__file__).resolve().parents[1] / 'app.py'
        app = AppTest.from_file(str(source), default_timeout=20).run()
        self.assertTrue(app.button(key='limpiar_lista_pegada').disabled)
        app.selectbox(key='proveedor_lista').select('Intcomex').run()
        app.text_area(key='texto_ingram').set_value('SKU\tPrecio\tStock\nA\t12,5\t3').run()
        app.button(key='procesar_listas').click().run()
        self.assertIn('lote', app.session_state)
        memoria = app.session_state['formatos_pegados'].copy()
        app.button(key='limpiar_lista_pegada').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.text_area(key='texto_ingram').value, '')
        self.assertNotIn('lote', app.session_state)
        self.assertEqual(app.selectbox(key='proveedor_lista').value, 'Intcomex')
        self.assertEqual(app.session_state['formatos_pegados'], memoria)
        self.assertTrue(app.button(key='limpiar_lista_pegada').disabled)

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
        self.assertEqual(app.selectbox(key='proveedor_lista').value, 'Intcomex')
        self.assertEqual(app.selectbox(key='moneda_lista_Intcomex').value, 'USD')
        app.button(key='procesar_listas').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.session_state['lote'][1]), 1)
        app.selectbox(key='moneda_lista_Intcomex').select('CLP').run()
        self.assertNotIn('lote', app.session_state)
        app.button(key='procesar_listas').click().run()
        self.assertEqual(app.session_state['lote'][1].iloc[0].currency, 'CLP')
        app.session_state['_files'] = [excel(PLANTILLAS['Ingram'], [['A', 12, 3]], name='Ingram.xlsx', second_sheet=True)]
        app.run()
        self.assertEqual(app.selectbox(key='proveedor_lista').value, 'Ingram')
        self.assertNotIn('lote', app.session_state)
        self.assertEqual(app.multiselect[0].value, [])
        app.multiselect[0].select('MATERIAL').select('OTRA').run()
        app.button(key='procesar_listas').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.session_state['lote'][1]), 2)


if __name__ == '__main__':
    unittest.main()
