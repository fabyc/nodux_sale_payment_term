# -*- coding: utf-8 -*-
#This file is part of the nodux_account_postdated_check module for Tryton.
#The COPYRIGHT file at the top level of this repository contains
#the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import ModelSingleton, ModelView, ModelSQL, fields
from trytond.transaction import Transaction
from trytond.pyson import Eval, In
from trytond.pool import Pool
from trytond.report import Report
import pytz
from datetime import datetime,timedelta
import time

conversor = None
try:
    from numword import numword_es
    conversor = numword_es.NumWordES()
except:
    print("Warning: Does not possible import numword module!")
    print("Please install it...!")


__all__ = [ 'AccountPostDateCheck']

_STATES = {
    'readonly': In(Eval('state'), ['posted']),
}

class AccountPostDateCheck(ModelSQL, ModelView):
    'Account Post Date Check'
    __name__ = 'account.postdated'
    _rec_name = 'number'


    @classmethod
    def __setup__(cls):
        super(AccountPostDateCheck, cls).__setup__()

    def deposit(self, move_lines):
        pool = Pool()
        Move = pool.get('account.move')
        MoveLine = pool.get('account.move.line')
        created_lines = MoveLine.create(move_lines)
        Move.post([self.move])
        Voucher = pool.get('account.voucher')
        Sale = pool.get('sale.sale')
        Invoice = pool.get('account.invoice')

        reconcile_lines = []

        for line in self.lines:
            voucher = Voucher.search([('number', '=', line.name)])
            sale = Sale.search([('id', '=', line.name)])

            if voucher:
                for v in voucher:
                    move = v.move
                line_r = MoveLine.search([('account', '=', line.account.id), ('move', '=', move.id)])
            if sale:
                for s in sale:
                    description = str(s.id)
                line_r = MoveLine.search([('account', '=', line.account.id), ('description', '=', description)])

            for line in line_r:
                reconcile_lines.append(line)
            for move_line in created_lines:
                if move_line.account.id == line.account.id:
                    reconcile_lines.append(move_line)
            MoveLine.reconcile(reconcile_lines)

        return True
