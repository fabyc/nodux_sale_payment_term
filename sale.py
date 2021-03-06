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
                    
                })
                
    @classmethod
    @ModelView.button_action('nodux_sale_payment_term.wizard_add_term')
    def wizard_add_term(cls, sales):
        pass
    

class AddTermForm(ModelView):
    'Add Term Form'
    __name__ = 'nodux_sale_payment_term.add_payment_term_form'
    
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
    creditos = fields.One2Many('sale_payment.payment', 'sale',
        'Formas de Pago')
    efectivo = fields.Numeric('Efectivo')
    cheque = fields.Numeric('Cheque')
    nro= fields.Char('Numero de cheque', size=20)
    banco = fields.Many2One('bank', 'Banco')
    valor = fields.Numeric('Total a pagar')
    dias_pagos = fields.Integer("Numero de dias para pagos", help=u"Ingrese el numero de dias a considerar para realizar el pago", states={
            'invisible': ~Eval('verifica_pagos', False),
            })
    titular = fields.Char('Titular de la cuenta')
    cuenta = fields.Char('Numero de la cuenta')
    
    @fields.depends('dias', 'creditos', 'efectivo', 'cheque', 'verifica_dias', 'valor')
    def on_change_dias(self):
        res = {}
        res['creditos'] = {}
        if self.dias:
            pool = Pool()
            Date = pool.get('ir.date')
            Sale = pool.get('sale.sale')
            """
            active_id = Transaction().context.get('active_id', False)
            sale = Sale(active_id)
            print "El active_id", active_id
            """
            
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
            monto_parcial = self.valor -(monto_efectivo + monto_cheque)
            
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
            
        return res          
    
    @fields.depends('pagos', 'creditos', 'efectivo', 'cheque', 'verifica_pagos', 'valor', 'dias_pagos')
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
            #monto_parcial = monto_efectivo + monto_cheque
            monto_parcial = self.valor -(monto_efectivo + monto_cheque)
            pagos = int(self.pagos)
            monto = (monto_parcial / pagos)
            monto = round(monto, 2)
            monto = str(monto)
            monto = Decimal(monto)
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
                                'monto': monto - restante,
                                'financiar':monto_parcial,
                                'valor_nuevo': monto,
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
        
    @fields.depends('pagos', 'creditos', 'efectivo', 'cheque', 'verifica_pagos', 'valor', 'dias_pagos')
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
            #monto_parcial = monto_efectivo + monto_cheque
            monto_parcial = self.valor -(monto_efectivo + monto_cheque)
            if self.pagos:
                monto = monto_parcial / self.pagos
                pagos = int(self.pagos)
            
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
            if self.creditos:
                res['creditos']['remove'] = [x['id'] for x in self.creditos]                   
        return res
        
    @fields.depends('pagos', 'creditos', 'efectivo', 'cheque', 'verifica_pagos', 'valor', 'dias_pagos', 'dias', 'verifica_dias')
    def on_change_creditos(self):
        if self.creditos:
            res = {}
            res['creditos'] = {}
            suma = Decimal(0.0)
            monto_disminuir = Decimal(0.0)
            cont = 0
            tam = len(self.creditos)
            for s in self.creditos:
                if s.financiar:
                    financiado = s.financiar
                    suma += s.monto
                    monto_pago = s.valor_nuevo
                
            if self.pagos:
                for s in self.creditos:
                    if s.monto != monto_pago:
                        cont += 1 
                        monto_disminuir += s.monto  
                monto_a = (financiado - monto_disminuir) / (tam-cont) 
                 
                for s in self.creditos:
                    if s.banco:
                        banco = s.banco.id
                    else:
                        banco = None
                        
                    if s.nro_cuenta:
                        nro_cuenta = s.nro_cuenta
                    else:
                        nro_cuenta = None
                    print "El banco y la cuenta ", banco, nro_cuenta
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
                         
            if self.creditos:
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
            Button('Imprimir Credito', 'print_', 'tryton-print'),
        ])
    add_ = StateTransition()
    print_ = StateAction('nodux_sale_payment_term.report_add_term')
    
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
        
        statements = Statement.search([
                ('state', '=', 'draft'),
                ], order=[('date', 'DESC')])
        account = (sale.party.account_receivable
            and sale.party.account_receivable.id
            or self.raise_user_error('party_without_account_receivable',
                error_args=(sale.party.name,)))
        
        if self.start.cheque:
            m_ch = self.start.cheque
        else:
            m_ch = Decimal(0.0)
            
        if self.start.efectivo:
            m_e = self.start.efectivo
        else:
            m_e = Decimal(0.0)
        sale.payment_amount = m_ch + m_e
        
        Term = Pool().get('account.invoice.payment_term')
        term = Term()
        PaymentTermLine = Pool().get('account.invoice.payment_term.line')
        
        if self.start.creditos :
            
            if self.start.verifica_dias == True:
                dias = self.start.dias
                lines= []
                term_line = PaymentTermLine(type='remainder', days=dias, divisor=Decimal(0.0))
                lines.append(term_line)
                term.name = 'Credito personalizado dias'
                term.lines = lines
                term.save()
                       
            if self.start.verifica_pagos == True :
                pagos = self.start.pagos
                dias_pagos = self.start.dias_pagos
                monto_inicial = self.start.valor
                lines= []
                cont = 1
                sequence = pagos
                for credito in self.start.creditos:
                    fecha = credito.fecha
                    monto = credito.monto
                    dias = str(fecha - datetime.now()).split('days')
                    dias[0].split(' ')
                    dias = dias[0]
                    percentage = Decimal(str(round((monto * 100)/monto_inicial, 8)))
                    divisor = Decimal(str(round(100/percentage, 8)))
                    
                    if cont != pagos:
                        term_line = PaymentTermLine(type='percent_on_total', days=dias, percentage=percentage, divisor= divisor)
                        lines.append(term_line)
                    
                    if cont == pagos:
                        term_line = PaymentTermLine(type='remainder', days=dias, divisor=Decimal(0.0))
                        lines.append(term_line)
                    cont += 1
                term.name = 'Credito personalizado pagos'
                term.lines = lines
                term.save()
                
                
        
        sale.payment_term = term
        sale.save()
        valor = m_ch + m_e
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
        return 'start'
        
    def transition_print_(self):
        return 'end'

    def do_print_(self, action):
        data = {}
        data['id'] = Transaction().context['active_ids'].pop()
        data['ids'] = [data['id']]
        return action, data
          
        
class Payment_Term(ModelView):
    'Payment Term Line'
    __name__ = 'sale_payment.payment'
    
    sale = fields.Many2One('sale.sale', 'Sale')
    fecha = fields.Date('Fecha de pago')
    monto = fields.Numeric("Valor a pagar")
    banco = fields.Many2One('bank', 'Banco')
    nro_cuenta = fields.Char('Numero de Cuenta')
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
        
        if invoices:
            for i in invoices:
                invoice = i
                invoice_e = 'true'
        else:
            invoice_e = 'false'
            invoice = sale
        localcontext['user'] = user
        localcontext['company'] = user.company
        localcontext['invoice'] = invoice
        localcontext['invoice_e'] = invoice_e
        
        return super(ReportAddTerm, cls).parse(report, records, data,
                localcontext=localcontext)     
