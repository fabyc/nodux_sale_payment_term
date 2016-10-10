#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, ModelView, MatchMixin, fields
from trytond.pyson import Eval
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

__all__ = ['Configuration']
__metaclass__ = PoolMeta


class Configuration:
    'Account Configuration'
    __name__ = 'account.configuration'

    default_account_check = fields.Many2One('account.account', 'Default Account Check')

    default_account_card = fields.Many2One('account.account', 'Default Account Card')
