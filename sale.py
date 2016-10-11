# This file is part of the sale_payment module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
#! -*- coding: utf8 -*-
from decimal import Decimal
from trytond.model import ModelView, fields, ModelSQL
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Bool, Eval, Not
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateTransition, Button, StateAction
from trytond import backend
from datetime import datetime,timedelta
from dateutil.relativedelta import relativedelta
from trytond.report import Report

__all__ = [ 'Sale', 'AddTermForm', 'WizardAddTerm', 'Payment_Term', 'ReportAddTerm']
__metaclass__ = PoolMeta
_ZERO = Decimal('0.0')
PRODUCT_TYPES = ['goods']


tipoPago = {
    '': '',
    'efectivo': 'Efectivo',
    'tarjeta': 'Tarjeta de Credito',
    'deposito': 'Deposito',
    'cheque': 'Cheque',
}

class Sale():
    __name__ = 'sale.sale'

    @classmethod
    def __setup__(cls):
        super(Sale, cls).__setup__()
        cls._buttons.update({
                'wizard_add_term': {
                    'invisible': ((Eval('state') != 'draft') | (Eval('invoice_state') != 'none')),
                    'readonly': ~Eval('lines', [0])
                    },

                'wizard_sale_payment': {
                    'readonly': ~Eval('lines', [0]),
                    'invisible': Eval('invoice_state') != 'none'
                    },
                'report_add_term': {
                    'invisible': ((Eval('state') == 'draft')),
                    },
                })

    @classmethod
    @ModelView.button_action('nodux_sale_payment_term.wizard_add_term')
    def wizard_add_term(cls, sales):
        pass

    @classmethod
    @ModelView.button_action('nodux_sale_payment_term.report_add_term')
    def report_add_term(cls, sales):
        pass

class AddTermForm(ModelView):
    'Add Term Form'
    __name__ = 'nodux_sale_payment_term.add_payment_term_form'

    valor = fields.Numeric('Total a pagar')

    verifica_dias = fields.Boolean("Credito por dias", help=u"Seleccione si desea realizar su pago en los dias siguientes", states={
            'invisible': Eval('verifica_pagos', True),
            })
    verifica_pagos = fields.Boolean("Credito por pagos", help=u"Seleccione si desea realizar sus pagos mensuales", states={
            'invisible': Eval('verifica_dias', True),
            })
    dias = fields.Integer("Numero de dias", help=u"Ingrese el numero de dias en los que se realizara el pago", states={
            'invisible': ~Eval('verifica_dias', False),
            })
    pagos = fields.Integer("Numero de pagos", help=u"Ingrese el numero de pagos en lo que realizara el pago total", states={
            'invisible': ~Eval('verifica_pagos', False),
            })
    dias_pagos = fields.Integer("Numero de dias para pagos", help=u"Ingrese el numero de dias a considerar para realizar el pago", states={
            'invisible': ~Eval('verifica_pagos', False),
            })
    creditos = fields.One2Many('sale_payment.payment', 'sale', 'Formas de Pago', states={
        'readonly': ~Eval('habilitar_credito', True),
    })
    efectivo = fields.Numeric('Efectivo')
    cheque = fields.Numeric('Cheque')
    tarjeta = fields.Numeric('Tarjeta')

    nro= fields.Char('Numero de cheque', size=20, states={
        'invisible' : ~Eval('cheque', [0])
    })
    banco = fields.Many2One('bank', 'Banco',states={
        'invisible' : ~Eval('cheque', [0])
    })
    titular = fields.Char('Titular de la cuenta',states={
        'invisible' : ~Eval('cheque', [0])
    })
    cuenta = fields.Char('Numero de la cuenta',states={
        'invisible' : ~Eval('cheque', [0])
    })
    habilitar_credito = fields.Boolean('Habilitar credito')
    no_tarjeta = fields.Char('No. de Tarjeta', states={
        'invisible': ~Eval('tarjeta', [0])
    })
    lote = fields.Char('No. de Lote', states= {
        'invisible' : ~Eval('tarjeta', [0])
    })
    tipo_tarjeta = fields.Many2One('sale.card', 'Tarjeta', states={
        'invisible': ~Eval('tarjeta', [0])
    })

    @fields.depends('dias', 'creditos', 'efectivo', 'cheque', 'verifica_dias',
    'valor', 'tarjeta')
    def on_change_dias(self):
        res = {}
        res['creditos'] = {}
        if self.dias:
            pool = Pool()
            Date = pool.get('ir.date')
            Sale = pool.get('sale.sale')

            if self.creditos:
                res['creditos']['remove'] = [x['id'] for x in self.creditos]

            if self.efectivo:
                monto_efectivo = self.efectivo
            else:
                monto_efectivo = Decimal(0.0)
            if self.cheque:
                monto_cheque = self.cheque
            else:
                monto_cheque = Decimal(0.0)
            if self.tarjeta:
                monto_tarjeta = self.tarjeta
            else:
                monto_tarjeta = Decimal(0.0)

            monto_parcial = self.valor -(monto_efectivo + monto_cheque + monto_tarjeta)

            dias = timedelta(days=int(self.dias))
            monto = monto_parcial
            fecha = datetime.now() + dias
            for c in self.creditos:
                if c.banco:
                    banco = c.banco.id
                if c.nro_cuenta:
                    nro_cuenta = c.nro_cuenta

            result = {
                'fecha': fecha,
                'monto': monto,
                'financiar':None,
                'valor_nuevo': None,
                'banco': None,
                'nro_cuenta': None,
            }

            res['creditos'].setdefault('add', []).append((0, result))
        else:
            if self.creditos:
                res['creditos']['remove'] = [x['id'] for x in self.creditos]
        res['habilitar_credito'] = True
        return res

    @fields.depends('pagos', 'creditos', 'efectivo', 'cheque', 'verifica_pagos',
    'valor', 'dias_pagos','tarjeta')
    def on_change_pagos(self):
        res = {}
        res['creditos'] = {}
        banco = None
        nro_cuenta = None
        if self.pagos:
            pool = Pool()
            Date = pool.get('ir.date')
            Sale = pool.get('sale.sale')

            if self.efectivo:
                monto_efectivo = self.efectivo
            else:
                monto_efectivo = Decimal(0.0)
            if self.cheque:
                monto_cheque = self.cheque
            else:
                monto_cheque = Decimal(0.0)
            if self.tarjeta:
                monto_tarjeta = self.tarjeta
            else:
                monto_tarjeta = Decimal(0.0)
            #monto_parcial = monto_efectivo + monto_cheque
            monto_parcial = self.valor -(monto_efectivo + monto_cheque + monto_tarjeta)
            pagos = int(self.pagos)
            monto = (monto_parcial / pagos)
            monto = Decimal(str(round(monto, 2)))
            comprobacion = monto * self.pagos
            restante = comprobacion - monto_parcial

            if self.creditos:
                res['creditos']['remove'] = [x['id'] for x in self.creditos]

            if comprobacion == monto_parcial:
                fecha_pagos = datetime.now()
                for p in range(pagos):

                    if self.dias_pagos == 30:
                        monto = monto
                        fecha = datetime.now() + relativedelta(months=(p+1))
                        result = {
                            'fecha': fecha,
                            'monto': monto,
                            'financiar':monto_parcial,
                            'valor_nuevo': monto,
                            'banco': banco,
                            'nro_cuenta':nro_cuenta,
                        }
                        res['creditos'].setdefault('add', []).append((0, result))
                    elif self.dias_pagos == None:
                        self.raise_user_error("Debe ingresar Numero de dias para pagos")
                    else :
                        monto = monto
                        dias = timedelta(days=int(self.dias_pagos))
                        fecha_pagos = fecha_pagos + dias
                        result = {
                            'fecha': fecha_pagos,
                            'monto': monto,
                            'financiar':monto_parcial,
                            'valor_nuevo': monto,
                            'banco': banco,
                            'nro_cuenta':nro_cuenta,
                        }
                        res['creditos'].setdefault('add', []).append((0, result))
            else:
                cont = 1
                fecha_pagos = datetime.now()
                for p in range(pagos):
                    if cont == pagos:
                        if self.dias_pagos == 30:
                            monto = monto
                            fecha = datetime.now() + relativedelta(months=(p+1))
                            result = {
                                'fecha': fecha,
                                'monto': monto - restante,
                                'financiar':monto_parcial,
                                'valor_nuevo': monto - restante,
                                'banco': banco,
                                'nro_cuenta':nro_cuenta,
                            }
                            res['creditos'].setdefault('add', []).append((0, result))
                        elif self.dias_pagos == None:
                            self.raise_user_error("Debe ingresar Numero de dias para pagos")
                        else :
                            monto = monto
                            dias = timedelta(days=int(self.dias_pagos))
                            fecha_pagos = fecha_pagos + dias
                            result = {
                                'fecha': fecha_pagos,
                                'monto': monto - restante,
                                'financiar':monto_parcial,
                                'valor_nuevo': monto - restante,
                                'banco': banco,
                                'nro_cuenta':nro_cuenta,
                            }
                            res['creditos'].setdefault('add', []).append((0, result))
                    else:
                        if self.dias_pagos == 30:
                            monto = monto
                            fecha = datetime.now() + relativedelta(months=(p+1))
                            result = {
                                'fecha': fecha,
                                'monto': monto,
                                'financiar':monto_parcial,
                                'valor_nuevo': monto,
                                'banco': banco,
                                'nro_cuenta':nro_cuenta,
                            }
                            res['creditos'].setdefault('add', []).append((0, result))
                        elif self.dias_pagos == None:
                            self.raise_user_error("Debe ingresar Numero de dias para pagos")
                        else :
                            monto = monto
                            dias = timedelta(days=int(self.dias_pagos))
                            fecha_pagos = fecha_pagos + dias
                            result = {
                                'fecha': fecha_pagos,
                                'monto': monto,
                                'financiar':monto_parcial,
                                'valor_nuevo': monto,
                                'banco': banco,
                                'nro_cuenta':nro_cuenta,
                            }
                            res['creditos'].setdefault('add', []).append((0, result))
                    cont += 1
        else:
            if self.creditos:
                res['creditos']['remove'] = [x['id'] for x in self.creditos]
        res['habilitar_credito'] = True
        return res

    @fields.depends('pagos', 'creditos', 'efectivo', 'cheque', 'verifica_pagos',
    'valor', 'dias_pagos', 'tarjeta')
    def on_change_dias_pagos(self):
        res = {}
        res['creditos'] = {}
        banco = None
        nro_cuenta = None
        if self.dias_pagos:
            pool = Pool()
            Date = pool.get('ir.date')
            Sale = pool.get('sale.sale')

            if self.creditos:
                res['creditos']['remove'] = [x['id'] for x in self.creditos]

            if self.efectivo:
                monto_efectivo = self.efectivo
            else:
                monto_efectivo = Decimal(0.0)
            if self.cheque:
                monto_cheque = self.cheque
            else:
                monto_cheque = Decimal(0.0)
            if self.tarjeta:
                monto_tarjeta = self.tarjeta
            else:
                monto_tarjeta = Decimal(0.0)
            #monto_parcial = monto_efectivo + monto_cheque
            monto_parcial = self.valor -(monto_efectivo + monto_cheque + monto_tarjeta)
            if self.pagos:
                monto = monto_parcial / self.pagos
                pagos = int(self.pagos)
                monto = Decimal(str(round(monto, 2)))
                comprobacion = monto * self.pagos
                restante = comprobacion - monto_parcial

                if comprobacion == monto_parcial:
                    fecha_pagos = datetime.now()
                    for p in range(pagos):

                        if self.dias_pagos == 30:
                            monto = monto
                            fecha = datetime.now() + relativedelta(months=(p+1))
                            result = {
                                'fecha': fecha,
                                'monto': monto,
                                'financiar':monto_parcial,
                                'valor_nuevo': monto,
                                'banco': banco,
                                'nro_cuenta':nro_cuenta,
                            }
                            res['creditos'].setdefault('add', []).append((0, result))
                        elif self.dias_pagos == None:
                            self.raise_user_error("Debe ingresar Numero de dias para pagos")
                        else :
                            monto = monto
                            dias = timedelta(days=int(self.dias_pagos))
                            fecha_pagos = fecha_pagos + dias
                            result = {
                                'fecha': fecha_pagos,
                                'monto': monto,
                                'financiar': monto_parcial,
                                'valor_nuevo': monto,
                                'banco': banco,
                                'nro_cuenta':nro_cuenta,
                            }
                            res['creditos'].setdefault('add', []).append((0, result))

                else:
                    cont = 1
                    fecha_pagos = datetime.now()
                    for p in range(pagos):
                        if cont == pagos:
                            if self.dias_pagos == 30:
                                monto = monto
                                fecha = datetime.now() + relativedelta(months=(p+1))
                                result = {
                                    'fecha': fecha,
                                    'monto': monto - restante,
                                    'financiar':monto_parcial,
                                    'valor_nuevo': monto - restante,
                                    'banco': banco,
                                    'nro_cuenta':nro_cuenta,
                                }
                                res['creditos'].setdefault('add', []).append((0, result))
                            elif self.dias_pagos == None:
                                self.raise_user_error("Debe ingresar Numero de dias para pagos")
                            else :
                                monto = monto
                                dias = timedelta(days=int(self.dias_pagos))
                                fecha_pagos = fecha_pagos + dias
                                result = {
                                    'fecha': fecha_pagos,
                                    'monto': monto - restante,
                                    'financiar':monto_parcial,
                                    'valor_nuevo': monto - restante,
                                    'banco': banco,
                                    'nro_cuenta':nro_cuenta,
                                }
                                res['creditos'].setdefault('add', []).append((0, result))
                        else:
                            if self.dias_pagos == 30:
                                monto = monto
                                fecha = datetime.now() + relativedelta(months=(p+1))
                                result = {
                                    'fecha': fecha,
                                    'monto': monto,
                                    'financiar':monto_parcial,
                                    'valor_nuevo': monto,
                                    'banco': banco,
                                    'nro_cuenta':nro_cuenta,
                                }
                                res['creditos'].setdefault('add', []).append((0, result))
                            elif self.dias_pagos == None:
                                self.raise_user_error("Debe ingresar Numero de dias para pagos")
                            else :
                                monto = monto
                                dias = timedelta(days=int(self.dias_pagos))
                                fecha_pagos = fecha_pagos + dias
                                result = {
                                    'fecha': fecha_pagos,
                                    'monto': monto,
                                    'financiar':monto_parcial,
                                    'valor_nuevo': monto,
                                    'banco': banco,
                                    'nro_cuenta':nro_cuenta,
                                }
                                res['creditos'].setdefault('add', []).append((0, result))
                        cont += 1
        else:
            if self.creditos:
                res['creditos']['remove'] = [x['id'] for x in self.creditos]
        return res

    @fields.depends('pagos', 'creditos', 'efectivo', 'cheque', 'verifica_pagos', 'valor', 'dias_pagos', 'dias', 'verifica_dias')
    def on_change_creditos(self):
        res = {}
        if self.creditos:

            res['creditos'] = {}
            suma = Decimal(0.0)
            suma_iguales = Decimal(0.0)
            monto_disminuir = Decimal(0.0)
            redondeo = Decimal(0.0)
            cont = 0
            cont_f = 1
            tam = len(self.creditos)
            valor_c = Decimal(0.0)
            for s in self.creditos:
                if (s.fecha != None) and (s.monto != None):
                    valor_c = s.financiar
                    if s.financiar:
                        financiado = s.financiar
                        suma += s.monto
                        monto_pago = s.valor_nuevo

            if self.pagos:
                for s in self.creditos:
                    if s.monto != monto_pago:
                        cont += 1
                        monto_disminuir += s.monto

                monto_a = Decimal(str(round(Decimal((financiado - monto_disminuir) / (tam-cont)),2)))
                comprobar = (monto_a *(tam-cont)) + monto_disminuir

                if comprobar == valor_c :
                    pass
                else:
                    redondeo = comprobar - valor_c

                for s in self.creditos:
                    if s.banco:
                        banco = s.banco.id
                    else:
                        banco = None

                    if s.nro_cuenta:
                        nro_cuenta = s.nro_cuenta
                    else:
                        nro_cuenta = None

                    if cont_f == len(self.creditos):
                        if s.monto != monto_pago:
                            result = {
                            'fecha': s.fecha,
                            'monto': s.monto-redondeo,
                            'financiar': s.financiar,
                            'valor_nuevo': monto_a,
                            'banco': banco,
                            'nro_cuenta': nro_cuenta,
                            }
                            res['creditos'].setdefault('add', []).append((0, result))
                        else:
                            result = {
                            'fecha': s.fecha,
                            'monto': monto_a-redondeo,
                            'financiar': s.financiar,
                            'valor_nuevo':monto_a,
                            'banco': banco,
                            'nro_cuenta':nro_cuenta,
                            }
                            res['creditos'].setdefault('add', []).append((0, result))
                    else:
                        if s.monto != monto_pago:
                            result = {
                            'fecha': s.fecha,
                            'monto': s.monto,
                            'financiar': s.financiar,
                            'valor_nuevo':monto_a,
                            'banco': banco,
                            'nro_cuenta': nro_cuenta,
                            }
                            res['creditos'].setdefault('add', []).append((0, result))
                        else:
                            result = {
                            'fecha': s.fecha,
                            'monto': monto_a,
                            'financiar': s.financiar,
                            'valor_nuevo':monto_a,
                            'banco': banco,
                            'nro_cuenta':nro_cuenta,
                            }
                            res['creditos'].setdefault('add', []).append((0, result))
                    cont_f += 1

            if self.creditos:
                for s in self.creditos:
                    if (s.fecha != None) and (s.monto != None):
                        res['creditos']['remove'] = [x['id'] for x in self.creditos]
        return res

    @staticmethod
    def default_dias_pagos():
        return int(30)

class WizardAddTerm(Wizard):
    'Wizard Add Term'
    __name__ = 'nodux_sale_payment_term.add_term'
    start = StateView('nodux_sale_payment_term.add_payment_term_form',
        'nodux_sale_payment_term.add_term_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Add', 'add_', 'tryton-ok'),
        ])
    add_ = StateTransition()

    def default_start(self, fields):
        pool = Pool()
        Sale = pool.get('sale.sale')
        default = {}
        sale = Sale(Transaction().context['active_id'])
        default['valor'] = sale.residual_amount
        default['titular'] = sale.party.name
        nombre = sale.party.name
        nombre = nombre.lower()
        if nombre == 'consumidor final':
            self.raise_user_error("No puede aplicar credito a cliente: CONSUMIDOR FINAL")
        elif sale.party.name == '9999999999999':
            self.raise_user_error("No puede aplicar credito a cliente: CONSUMIDOR FINAL")
        else:
            return default

    def transition_add_(self):
        pool = Pool()
        Sale = pool.get('sale.sale')
        active_id = Transaction().context.get('active_id', False)
        sale = Sale(active_id)
        Statement = pool.get('account.statement')
        StatementLine = pool.get('account.statement.line')
        Date = pool.get('ir.date')
        valor_conciliar = Decimal(0.0)
        statements = Statement.search([
                ('state', '=', 'draft'),
                ], order=[('date', 'DESC')])
        statements_cheque = Statement.search([
                ('state', '=', 'draft'),
                ('tipo_pago', '=', 'cheque')
                ], order=[('date', 'DESC')])

        account = (sale.party.account_receivable
            and sale.party.account_receivable.id
            or self.raise_user_error('party_without_account_receivable',
                error_args=(sale.party.name,)))

        Period = pool.get('account.period')
        Move = pool.get('account.move')

        move_lines = []
        line_move_ids = []
        move, = Move.create([{
            'period': Period.find(sale.company.id, date=sale.sale_date),
            'journal': 1,
            'date': sale.sale_date,
            'origin': str(sale),
            'description': str(sale.id),
        }])

        postdated_lines = None
        if self.start.cheque:
            if self.start.cheque > Decimal(0.0):
                Configuration = pool.get('account.configuration')
                if Configuration(1).default_account_check:
                    account_check = Configuration(1).default_account_check
                else:
                    self.raise_user_error('No ha configurado la cuenta por defecto para Cheques. \nDirijase a Financiero-Configuracion-Configuracion Contable')

                move_lines.append({
                    'description' : str(sale.id),
                    'debit': self.start.cheque,
                    'credit': Decimal(0.0),
                    'account': account_check,
                    'move': move.id,
                    'journal': 1,
                    'period': Period.find(sale.company.id, date=sale.sale_date),
                })

                m_ch = self.start.cheque
                postdated_lines = []
                if self.start.banco:
                    pass
                else:
                    self.raise_user_error('Ingrese el banco')

                if self.start.nro:
                    pass
                else:
                    self.raise_user_error('Ingrese el numero de cheque')

                if self.start.cuenta:
                    pass
                else:
                    self.raise_user_error('Ingrese el numero de cuenta')

                postdated_lines.append({
                    'reference': str(sale.id),
                    'name': str(sale.id),
                    'amount': Decimal(m_ch),
                    'account': account_check,
                    'date_expire': sale.sale_date,
                    'date': sale.sale_date,
                    'num_check' : self.start.nro,
                    'num_account' : self.start.cuenta,
                })

            pool = Pool()
            Period = pool.get('account.period')
            Move = pool.get('account.move')
            Invoice = pool.get('account.invoice')

            if postdated_lines != None:
                Postdated = pool.get('account.postdated')
                postdated = Postdated()
                for line in postdated_lines:
                    date = line['date']
                    postdated.postdated_type = 'check'
                    postdated.reference = str(sale.id)
                    postdated.party = sale.party
                    postdated.post_check_type = 'receipt'
                    postdated.journal = 1
                    postdated.lines = postdated_lines
                    postdated.state = 'draft'
                    postdated.date = sale.sale_date
                    postdated.save()
        else:
            m_ch = Decimal(0.0)

        if self.start.tarjeta:
            if self.start.tarjeta > Decimal(0.0):

                Configuration = pool.get('account.configuration')
                if Configuration(1).default_account_card:
                    account_card = Configuration(1).default_account_card
                else:
                    self.raise_user_error('No ha configurado la cuenta por defecto para Cheques. \nDirijase a Financiero-Configuracion-Configuracion Contable')

                move_lines.append({
                    'description' : str(sale.id),
                    'debit': self.start.tarjeta,
                    'credit': Decimal(0.0),
                    'account': account_card,
                    'move': move.id,
                    'journal': 1,
                    'period': Period.find(sale.company.id, date=sale.sale_date),
                })
                m_tc = self.start.tarjeta
                postdated_lines = []
                if self.start.no_tarjeta:
                    pass
                else:
                    self.raise_user_error('Ingrese el numero de Tarjeta')

                if self.start.tipo_tarjeta:
                    pass
                else:
                    self.raise_user_error('Ingrese la Tarjeta')

                if self.start.lote:
                    pass
                else:
                    self.raise_user_error('Ingrese el no. de lote de la tarjeta')

                postdated_lines.append({
                    'reference': str(sale.id),
                    'name': str(sale.id),
                    'amount': Decimal(m_tc),
                    'account': account_card,
                    'date_expire': sale.sale_date,
                    'date': sale.sale_date,
                    'num_check' : self.start.no_tarjeta,
                    'num_account' : self.start.lote,
                })

            if postdated_lines != None:
                Postdated = pool.get('account.postdated')
                postdated = Postdated()
                for line in postdated_lines:
                    date = line['date']
                    postdated.postdated_type = 'card'
                    postdated.reference = str(sale.id)
                    postdated.party = sale.party
                    postdated.post_check_type = 'receipt'
                    postdated.journal = 1
                    postdated.lines = postdated_lines
                    postdated.state = 'draft'
                    postdated.date = sale.sale_date
                    postdated.save()

        else:
            m_tc = Decimal(0.0)

        if (m_tc + m_ch) > Decimal(0.0):
            move_lines.append({
                'description': str(sale.id),
                'debit': Decimal(0.0),
                'credit': m_tc + m_ch,
                'account': sale.party.account_receivable.id,
                'move': move.id,
                'journal': 1,
                'period': Period.find(sale.company.id, date=sale.sale_date),
                'date': sale.sale_date,
                'party': sale.party.id,
            })
        print "Las lineas del asiento", move, move_lines
        self.create_move(move_lines, move)

        if self.start.efectivo:
            m_e = self.start.efectivo
        else:
            m_e = Decimal(0.0)
        sale.payment_amount = m_e

        Term = Pool().get('account.invoice.payment_term')
        term = Term()
        PaymentTermLine = Pool().get('account.invoice.payment_term.line')

        if self.start.creditos :
            for credito in self.start.creditos:
                if credito.banco:
                    valor_conciliar += credito.monto

            if self.start.verifica_dias == True:
                terms = Term.search([('name','=', 'Credito personalizado dias')])
                for t in terms:
                    term = t
                    eliminar =  term.id
                    cursor = Transaction().cursor
                    cursor.execute('DELETE FROM account_invoice_payment_term_line WHERE payment = %s' % eliminar)

                dias = self.start.dias

                lines= []
                term_line = PaymentTermLine(payment=term.id, type='remainder', days=dias, divisor=Decimal(0.0))
                lines.append(term_line)
                term.lines = lines
                term.save()

            if self.start.verifica_pagos == True :
                pagos = self.start.pagos
                dias_pagos = self.start.dias_pagos
                monto_inicial = self.start.valor
                lines= []
                cont_ = 1
                sequence = pagos
                len_ = len(self.start.creditos)
                cont = 1
                for credito in self.start.creditos:
                    if cont_ == 1:
                        fecha_inicial= credito.fecha
                    if cont_ == len_:
                        fecha_final= credito.fecha
                    cont_ += 1
                terms = Term.search([('name','=', 'Credito personalizado pagos')])
                for t in terms:
                    term = t
                    eliminar =  term.id
                    cursor = Transaction().cursor
                    cursor.execute('DELETE FROM account_invoice_payment_term_line WHERE payment = %s' % eliminar)

                if fecha_inicial < fecha_final:
                    for credito in self.start.creditos:
                        fecha = credito.fecha
                        monto = credito.monto
                        dias = str(fecha - datetime.now()).split('days')
                        dias[0].split(' ')
                        dias = int(dias[0])
                        percentage = Decimal(str(round((monto * 100)/monto_inicial, 8)))
                        divisor = Decimal(str(round(100/percentage, 8)))
                        if dias_pagos == 30:
                            if cont != pagos:
                                term_line = PaymentTermLine(payment=term.id, type='percent_on_total', months=cont, percentage=percentage, divisor= divisor)
                                lines.append(term_line)

                            if cont == pagos:
                                term_line = PaymentTermLine(payment=term.id, type='remainder', months=cont, divisor=Decimal(0.0))
                                lines.append(term_line)
                        else:
                            if cont != pagos:
                                term_line = PaymentTermLine(payment=term.id, type='percent_on_total', days=(dias_pagos*cont), percentage=percentage, divisor= divisor)
                                lines.append(term_line)

                            if cont == pagos:
                                term_line = PaymentTermLine(payment=term.id, type='remainder', days=(dias_pagos*cont), divisor=Decimal(0.0))
                                lines.append(term_line)
                        cont += 1
                    term.lines = lines
                    term.save()

                else:
                    creditos = self.start.creditos
                    creditos.sort(reverse=True)

                    for credito in creditos:
                        fecha = credito.fecha
                        monto = credito.monto
                        dias = str(fecha - datetime.now()).split('days')
                        dias[0].split(' ')
                        dias = int(dias[0])
                        percentage = Decimal(str(round((monto * 100)/monto_inicial, 8)))
                        divisor = Decimal(str(round(100/percentage, 8)))

                        if dias_pagos == 30:
                            if cont != pagos:
                                term_line = PaymentTermLine(payment=term.id, type='percent_on_total', months=cont, percentage=percentage, divisor= divisor)
                                lines.append(term_line)

                            if cont == pagos:
                                term_line = PaymentTermLine(payment=term.id, type='remainder', months=cont, divisor=Decimal(0.0))
                                lines.append(term_line)
                        else:
                            if cont != pagos:
                                term_line = PaymentTermLine(payment=term.id, type='percent_on_total', days=(dias_pagos*cont), percentage=percentage, divisor= divisor)
                                lines.append(term_line)

                            if cont == pagos:
                                term_line = PaymentTermLine(type='remainder', days=(dias_pagos*cont), divisor=Decimal(0.0))
                                lines.append(term_line)
                        cont += 1
                    term.lines = lines
                    term.save()

        sale.payment_term = term
        sale.save()
        valor = m_e
        if valor_conciliar != Decimal(0.0):
            payment_cheque = StatementLine(
                    statement=statements_cheque[0].id,
                    date=Date.today(),
                    amount=valor_conciliar,
                    party=sale.party.id,
                    account=account,
                    description=sale.reference,
                    sale=active_id
                    )
            payment_cheque.save()

        if valor != 0:
            payment = StatementLine(
                    statement=statements[0].id,
                    date=Date.today(),
                    amount=valor,
                    party=sale.party.id,
                    account=account,
                    description=sale.reference,
                    sale=active_id
                    )
            payment.save()
        Sale.workflow_to_end([sale])
        return 'end'

    def create_move(self, move_lines, move):
        pool = Pool()
        Move = pool.get('account.move')
        MoveLine = pool.get('account.move.line')
        Invoice = pool.get('account.invoice')
        created_lines = MoveLine.create(move_lines)
        Move.post([move])

        return True

class Payment_Term(ModelView):
    'Payment Term Line'
    __name__ = 'sale_payment.payment'

    sale = fields.Many2One('sale.sale', 'Sale')
    fecha = fields.Date('Fecha de pago')
    monto = fields.Numeric("Valor a pagar")
    banco = fields.Many2One('bank', 'Banco')
    nro_document = fields.Char('Numero de documento')
    nro_cuenta = fields.Char('Numero de cuenta')
    financiar = fields.Numeric("Total a financiar")
    valor_nuevo = fields.Numeric("Valor nuevo")

class ReportAddTerm(Report):
    __name__ = 'nodux_sale_payment_term.report_add_term'

    @classmethod
    def parse(cls, report, records, data, localcontext):
        pool = Pool()
        User = Pool().get('res.user')
        user = User(Transaction().user)
        sale = records[0]

        Invoice = pool.get('account.invoice')
        Sale = pool.get('sale.sale')
        sale = records[0]
        invoices = Invoice.search([('description', '=', sale.reference), ('description', '!=', None)])
        Statement = pool.get('account.statement')
        StatementLine = pool.get('account.statement.line')
        statement_cheques = Statement.search([('tipo_pago', '=', 'cheque')])
        statement_cheque = None
        statement_line = None

        if statement_cheques:
            for s in statement_cheques:
                statement_cheque = s
        if statement_cheque:
            statement_line = StatementLine.search([('statement', '=', statement_cheque.id), ('sale', '=', sale.id)])

        if invoices:
            for i in invoices:
                invoice = i
                invoice_e = 'true'
        else:
            invoice_e = 'false'
            invoice = sale

        if statement_line:
            cheque = 'true'
        else:
            cheque = 'false'

        localcontext['user'] = user
        localcontext['company'] = user.company
        localcontext['invoice'] = invoice
        localcontext['invoice_e'] = invoice_e
        localcontext['cheque']=cheque
        return super(ReportAddTerm, cls).parse(report, records, data,
                localcontext=localcontext)
