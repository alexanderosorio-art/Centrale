"""Registro único. Cada módulo expone NOMBRE, PATRON, MONEDA y leer."""
from . import (intcomex, ingram, kepler, tecnoglobal, coimco, fujicorp, nexsys,
               solutionbox, demco, gerona, facciatech, gtc_ribbon, otro)

MODULOS = (intcomex, ingram, kepler, tecnoglobal, coimco, fujicorp, nexsys,
           solutionbox, demco, gerona, facciatech, gtc_ribbon, otro)
REGISTRO = {modulo.NOMBRE: modulo for modulo in MODULOS}
PROVEEDORES_CONFIGURADOS = [m.NOMBRE for m in MODULOS if m.leer is not None]
PROVEEDORES_SIN_REGLAS = [m.NOMBRE for m in MODULOS if m.leer is None]
# Orden histórico del selector, independiente del orden de detección.
ORDEN_SELECTOR = [ingram, intcomex, tecnoglobal, coimco, fujicorp, kepler,
                  nexsys, solutionbox, demco, gerona, facciatech, gtc_ribbon, otro]
OPCIONES_PROVEEDORES = ['Seleccionar...', *(m.NOMBRE for m in ORDEN_SELECTOR)]
