# This file is part of the sale_payment module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from .sale import *
from .postdated_check import *
from .account import *

def register():
    Pool.register(
        Sale,
        AddTermForm,
        Payment_Term,
        AccountPostDateCheck,
        Configuration,
        module='nodux_sale_payment_term', type_='model')
    Pool.register(
        WizardAddTerm,
        module='nodux_sale_payment_term', type_='wizard')
    Pool.register(
        ReportAddTerm,
        module='nodux_sale_payment_term', type_='report')
