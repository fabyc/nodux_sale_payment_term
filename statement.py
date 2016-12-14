#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.model import Workflow, ModelView, ModelSQL, fields
from trytond.pyson import Eval, If, Bool
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

__all__ = ['Line']
__metaclass__ = PoolMeta

class Line:
    __name__ = 'account.statement.line'

    def create_move(self):
        pool = Pool()
        Move = pool.get('account.move')
        Period = pool.get('account.period')
        Invoice = pool.get('account.invoice')
        Currency = pool.get('currency.currency')
        MoveLine = pool.get('account.move.line')

        if self.move:
            return

        period_id = Period.find(self.statement.company.id, date=self.date)

        move_lines = self._get_move_lines()
        move = Move(
            period=period_id,
            journal=self.statement.journal.journal,
            date=self.date,
            origin=self,
            lines=move_lines,
            )
        move.save()

        self.write([self], {
                'move': move.id,
                })

        if self.invoice:
            Postdated = pool.get('account.postdated')

            with Transaction().set_context(date=self.invoice.currency_date):
                amount = Currency.compute(self.statement.journal.currency,
                    self.amount, self.statement.company.currency)

            reconcile_lines = self.invoice.get_reconcile_lines_for_amount(
                abs(amount))

            moves_payment = Move.search([('description', '=', self.description)])


            postdateds = Move.search([('description', '=', self.id)])


            lines_advanced = []
            account = self.party.account_receivable
            amount2 = Decimal(0.0)
            amount3 = Decimal(0.0)

            for postdated in postdateds:
                if not postdated:
                    continue
                for line in postdated.lines:
                    if (not line.reconciliation and line.account.id == account.id):
                        lines_advanced.append(line)
                        amount3 += line.debit - line.credit

            for move_payment in moves_payment:
                if not move_payment:
                    continue
                for line in move_payment.lines:
                    if (not line.reconciliation and
                            line.account.id == account.id):
                        lines_advanced.append(line)
                        amount2 += line.debit - line.credit

            for move_line in move.lines:
                if move_line.account == self.invoice.account:
                    Invoice.write([self.invoice], {
                            'payment_lines': [('add', [move_line.id])],
                            })
                    break

            for move_line_advanced in lines_advanced:
                if move_line_advanced.account == self.invoice.account:
                    Invoice.write([self.invoice], {
                            'payment_lines': [('add', [move_line_advanced.id])],
                            })
                    break

            if lines_advanced:
                if amount2 < 0:
                    amount2 = Decimal(amount2*-1)
                if amount3 < 0:
                    amount3 = Decimal(amount3*-1)
                if (reconcile_lines[1] - (amount2 + amount3)) == Decimal('0.0'):
                    lines = reconcile_lines[0] + [move_line] + lines_advanced
                    MoveLine.reconcile(lines)
            else:
                if reconcile_lines[1] == Decimal('0.0'):
                    lines = reconcile_lines[0] + [move_line]
                    MoveLine.reconcile(lines)
        return move
