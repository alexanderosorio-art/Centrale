"""Regresión de precios de oferta ASUS Nexsys, sin datos comerciales adjuntos."""
import unittest
from test_providers import excel, FECHA
from processing import procesar_archivos


class NexsysOfferTests(unittest.TestCase):
    def test_lowest_positive_price_and_invalid_offers(self):
        for offer_header in ['Precio Oferta', 'Precios Ofertas USD ', 'OFERTA']:
            with self.subTest(header=offer_header):
                headers = ['Numero de  Parte ', 'Modelo', 'Precio USD (s/IVA)',
                           offer_header, 'Stock Referencial', 'OFERTA X VOLUMEN']
                rows = [
                    ['PN-A', 'Modelo A', '1150.-', '910.-', 11, 500],
                    ['PN-B', 'Modelo B', 1150, None, 1, 500],
                    ['PN-C', 'Modelo C', 1150, 0, 1, 500],
                    ['PN-D', 'Modelo D', 1150, -5, 1, 500],
                    ['PN-E', 'Modelo E', 1150, 'Consultar', 1, 500],
                    ['PN-F', 'Modelo F', 1150, 1200, 1, 500],
                    ['PN-G', 'Modelo G', None, 910, 1, 500],
                    ['PN-H', 'Modelo H', 1150, 910, 0, 500],
                ]
                summary, result = procesar_archivos([excel(headers, rows)], FECHA,
                                                    'Nexsys', permitir_pn=True)
                self.assertEqual(summary.iloc[0]['Estado'], 'Procesado')
                self.assertEqual(list(result.currency_unaware_cost_neto),
                                 [910, 1150, 1150, 1150, 1150, 1150, 910])
                self.assertEqual(result.iloc[0].quantity, 11)
                self.assertEqual(result.iloc[0].mpn, 'PN-A')
                self.assertEqual(set(result.currency), {'USD'})

    def test_offer_rule_does_not_change_other_providers(self):
        headers = ['CODIGO', 'DESCRIPCION', 'PRECIO', 'PRECIO OFERTA', 'STOCK']
        for provider, expected in [('Nexsys', 910), ('Coimco', 1150), ('Tecnoglobal', 1150), ('Fujicorp', 910)]:
            with self.subTest(provider=provider):
                _, result = procesar_archivos([excel(headers, [['PN-A', 'Producto', 1150, 910, 11]])],
                                              FECHA, provider)
                self.assertEqual(result.iloc[0].currency_unaware_cost_neto, expected)


if __name__ == '__main__':
    unittest.main()
