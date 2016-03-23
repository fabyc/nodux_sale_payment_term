# This file is part of the sale_payment module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
#! -*- coding: utf8 -*-
from decimal import Decimal
from trytond.model import ModelView, fields, ModelSQL
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Bool, Eval, Not
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond import backend
from datetime import datetime,timedelta
from dateutil.relativedelta import relativedelta

__all__ = [ 'Sale', 'AddTermForm', 'WizardAddTerm', 'Payment_Term']
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
                    'invisible': Eval('state') != 'draft'
                    },
                    
                })
                
    @classmethod
    @ModelView.button_action('nodux_sale_payment.wizard_add_term')
    def wizard_add_term(cls, sales):
        pass
    

class AddTermForm(ModelView):
    'Add Term Form'
    __name__ = 'nodux_sale_payment.add_payment_term_form'
    
    verifica_dias = fields.Boolean("Credito por dias", help=u"Seleccione si desea realizar su pago en los dias siguientes", states={
            'invisible': Eval('verifica_pagos', True),
            })
    verifica_pagos = fields.Boolean("Credito por pagos", help=u"Seleccione si desea realizar sus pagos mensuales", states={
            'invisible': Eval('verifica_dias', True),
            })
    dias = fields.Numeric("Numero de dias", help=u"Ingrese el numero de dias en los que se realizara el pago", states={
            'invisible': ~Eval('verifica_dias', False),
            })
    pagos = fields.Numeric("Numero de pagos", help=u"Ingrese el numero de pagos en lo que realizara el pago total", states={
            'invisible': ~Eval('verifica_pagos', False),
            })
    creditos = fields.One2Many('sale_payment.payment', 'sale',
        'Formas de Pago')
    efectivo = fields.Numeric('Efectivo')
    cheque = fields.Numeric('Cheque')
    nro= fields.Char('Numero de cheque', size=20)
    banco = fields.Many2One('bank', 'Banco')
    valor = fields.Numeric('Total a pagar')
    dias_pagos = fields.Numeric("Numero de dias para pagos", help=u"Ingrese el numero de dias a considerar para realizar el pago", states={
            'invisible': ~Eval('verifica_pagos', False),
            })
    titular = fields.Char('Titular de la cuenta')
    cuenta = fields.Char('Numero de la cuenta')
    
    @fields.depends('dias', 'creditos', 'efectivo', 'cheque', 'verifica_dias', 'valor')
    def on_change_dias(self):
        if self.dias:
            print "El valor es ", self.valor
            pool = Pool()
            Date = pool.get('ir.date')
            Sale = pool.get('sale.sale')
            
            """
            active_id = Transaction().context.get('active_id', False)
            sale = Sale(active_id)
            print "El active_id", active_id
            """
            res = {}
            res['creditos'] = {}
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
            result = {
                'fecha': fecha,
                'monto': monto,
            }
            
            res['creditos'].setdefault('add', []).append((0, result))
            print res
            return res          
    
    @fields.depends('pagos', 'creditos', 'efectivo', 'cheque', 'verifica_pagos', 'valor', 'dias_pagos')
    def on_change_pagos(self):
        if self.pagos:
            pool = Pool()
            Date = pool.get('ir.date')
            Sale = pool.get('sale.sale')
            """
            active_id = Transaction().context.get('active_id', False)
            sale = Sale(active_id)
            print "El active_id", active_id
            """
            
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
            monto = monto_parcial / self.pagos
            pagos = int(self.pagos)
            
            res = {}
            res['creditos'] = {}
            if self.creditos:
                res['creditos']['remove'] = [x['id'] for x in self.creditos]
            
            fecha_pagos = datetime.now()
            for p in range(pagos):
                
                if self.dias_pagos == 30:
                    monto = monto
                    fecha = datetime.now() + relativedelta(months=(p+1))
                    result = {
                        'fecha': fecha,
                        'monto': monto,
                        'financiar':monto_parcial,
                        'valor_nuevo': monto
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
                        'valor_nuevo': monto
                    }
                    res['creditos'].setdefault('add', []).append((0, result))
                    
            print res
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
                financiado = s.financiar
                suma += s.monto
                monto_pago = s.valor_nuevo
                
            if self.pagos:
                print "Cuando es el monto de pago original ", monto_pago
                for s in self.creditos:
                    print "Monto con q se compara ",s.monto
                    if s.monto != monto_pago:
                        cont += 1 
                        monto_disminuir += s.monto  
                monto_a = (financiado - monto_disminuir) / (tam-cont) 
                 
                for s in self.creditos:
                    if s.monto != monto_pago:
                        result = {
                        'fecha': s.fecha,
                        'monto': s.monto,
                        'financiar': s.financiar,
                        'valor_nuevo':monto_a
                        } 
                        res['creditos'].setdefault('add', []).append((0, result))   
                    else:   
                        result = {
                        'fecha': s.fecha,
                        'monto': monto_a,
                        'financiar': s.financiar,
                        'valor_nuevo':monto_a
                        }  
                        res['creditos'].setdefault('add', []).append((0, result))     
                         
                print "Nuevos valores financiado ",financiado, "pagos ", self.pagos, "monto_disminuir ", monto_disminuir, "tamanio", tam, "cambiados ", cont, "valor nuevo ", monto_a     
                        
            if self.dias:
                print "Ingresa al metodo ****"
            if self.creditos:
                res['creditos']['remove'] = [x['id'] for x in self.creditos]
                    
            return res
            
    @staticmethod
    def default_dias_pagos():
        return Decimal(30.00)
                 
class WizardAddTerm(Wizard):
    'Wizard Add Term'
    __name__ = 'nodux_sale_payment.add_term'
    start = StateView('nodux_sale_payment.add_payment_term_form',
        'nodux_sale_payment.add_term_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Add', 'add_', 'tryton-ok'),
            Button('Imprimir Credito', 'print_', 'tryton-ok'),
        ])
    add_ = StateTransition()
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
        print "Esto es lo que recibe **", self.start.creditos #aqui estan todas las lineas de credito que seran para los asientos contables
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
        print "Valores que se pagaran" ,m_ch, m_e    
        sale.payment_amount = m_ch + m_e
        sale.save()
        
        valor = m_ch + m_e
        if valor != 0:
            payment = StatementLine(
                    statement=statements[0].id,
                    date=Date.today(),
                    amount=(m_ch + m_e),
                    party=sale.party.id,
                    account=account,
                    description=sale.reference,
                    sale=active_id
                    )
            payment.save()
        Sale.workflow_to_end([sale])
        
        return 'end'
class Payment_Term(ModelView):
    'Payment Term Line'
    __name__ = 'sale_payment.payment'
    
    sale = fields.Many2One('sale.sale', 'Sale')
    fecha = fields.Date('Fecha de pago')
    monto = fields.Numeric("Valor a pagar")
    banco = fields.Many2One('bank', 'Banco')
    numero_cuenta = fields.Many2One('bank.account', 'Numero de Cuenta')
    financiar = fields.Numeric("Total a financiar")
    valor_nuevo = fields.Numeric("Valor nuevo")
