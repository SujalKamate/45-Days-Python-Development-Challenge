"""
Object-Oriented Bank Account Simulation with Transaction History
Supports deposit, withdraw, balance, overdraft protection, and mini statement.
"""

from datetime import datetime
from typing import List, Optional


class Transaction:
    def __init__(self, t_type: str, amount: float, balance_after: float, note: str = ""):
        self.t_type = t_type
        self.amount = amount
        self.balance_after = balance_after
        self.note = note
        self.timestamp = datetime.now()

    def __str__(self):
        sign = "+" if self.t_type in ("DEPOSIT", "INTEREST") else "-"
        return (
            f"  {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}  "
            f"{self.t_type:<12}  {sign}₹{self.amount:>10.2f}  "
            f"Balance: ₹{self.balance_after:>10.2f}  {self.note}"
        )


class BankAccount:
    MINIMUM_BALANCE = 500.0
    INTEREST_RATE = 0.035  # 3.5% annual

    def __init__(self, holder: str, account_number: str, initial_deposit: float = 0):
        if initial_deposit < self.MINIMUM_BALANCE:
            raise ValueError(
                f"Initial deposit must be at least ₹{self.MINIMUM_BALANCE:.2f}"
            )
        self.holder = holder
        self.account_number = account_number
        self._balance = initial_deposit
        self._transactions: List[Transaction] = []
        self._locked = False

        self._log("DEPOSIT", initial_deposit, "Account opened")

    def _log(self, t_type: str, amount: float, note: str = ""):
        txn = Transaction(t_type, amount, self._balance, note)
        self._transactions.append(txn)

    @property
    def balance(self):
        return self._balance

    def deposit(self, amount: float, note: str = ""):
        if self._locked:
            raise PermissionError("Account is locked.")
        if amount <= 0:
            raise ValueError("Deposit amount must be positive.")
        self._balance += amount
        self._log("DEPOSIT", amount, note)
        print(f"  ✓ Deposited ₹{amount:.2f}. New balance: ₹{self._balance:.2f}")

    def withdraw(self, amount: float, note: str = ""):
        if self._locked:
            raise PermissionError("Account is locked.")
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive.")
        if self._balance - amount < self.MINIMUM_BALANCE:
            raise ValueError(
                f"Insufficient funds. Minimum balance of ₹{self.MINIMUM_BALANCE:.2f} required. "
                f"Max withdraw: ₹{max(0, self._balance - self.MINIMUM_BALANCE):.2f}"
            )
        self._balance -= amount
        self._log("WITHDRAWAL", amount, note)
        print(f"  ✓ Withdrew ₹{amount:.2f}. New balance: ₹{self._balance:.2f}")

    def transfer(self, target: 'BankAccount', amount: float):
        self.withdraw(amount, f"Transfer to {target.account_number}")
        target.deposit(amount, f"Transfer from {self.account_number}")
        print(f"  ✓ Transferred ₹{amount:.2f} to {target.holder}")

    def apply_interest(self, months: int = 1):
        monthly_rate = self.INTEREST_RATE / 12
        interest = round(self._balance * monthly_rate * months, 2)
        self._balance += interest
        self._log("INTEREST", interest, f"{months} month(s) at {self.INTEREST_RATE*100}% p.a.")
        print(f"  ✓ Interest of ₹{interest:.2f} applied.")

    def lock(self):
        self._locked = True
        print(f"  ⚠ Account {self.account_number} locked.")

    def unlock(self):
        self._locked = False
        print(f"  ✓ Account {self.account_number} unlocked.")

    def mini_statement(self, last_n: int = 10):
        print(f"\n  {'═'*80}")
        print(f"  MINI STATEMENT — {self.holder}  |  A/C: {self.account_number}")
        print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  {'═'*80}")
        txns = self._transactions[-last_n:]
        if not txns:
            print("  No transactions found.")
        for t in txns:
            print(t)
        print(f"  {'─'*80}")
        print(f"  Current Balance : ₹{self._balance:>10.2f}")
        print(f"  Total Txns Shown: {len(txns)} of {len(self._transactions)}")
        print(f"  {'═'*80}\n")

    def summary(self):
        total_dep = sum(t.amount for t in self._transactions if t.t_type in ("DEPOSIT", "INTEREST"))
        total_wdl = sum(t.amount for t in self._transactions if t.t_type == "WITHDRAWAL")
        print(f"\n  Account Summary — {self.holder}")
        print(f"  Account No     : {self.account_number}")
        print(f"  Total Deposits : ₹{total_dep:.2f}")
        print(f"  Total Withdraws: ₹{total_wdl:.2f}")
        print(f"  Net Balance    : ₹{self._balance:.2f}")
        print(f"  Transactions   : {len(self._transactions)}")
        print(f"  Status         : {'🔒 Locked' if self._locked else '✓ Active'}\n")


def main():
    print("╔══════════════════════════════════════════╗")
    print("║   Bank Account Simulation v1.0           ║")
    print("╚══════════════════════════════════════════╝\n")

    try:
        acc1 = BankAccount("Alice Sharma", "ACC001", 5000)
        acc2 = BankAccount("Bob Verma", "ACC002", 2000)

        acc1.deposit(1500, "Salary")
        acc1.withdraw(800, "Grocery")
        acc1.withdraw(200, "Transport")
        acc1.deposit(3000, "Freelance")
        acc1.apply_interest(3)
        acc1.transfer(acc2, 1000)

        acc2.deposit(500, "Gift")
        acc2.withdraw(700, "Rent")

        acc1.mini_statement(last_n=10)
        acc2.mini_statement(last_n=5)

        acc1.summary()
        acc2.summary()

        # Test overdraft protection
        print("  Testing overdraft protection:")
        try:
            acc2.withdraw(99999)
        except ValueError as e:
            print(f"  ✗ Error caught: {e}")

        # Test lock
        acc1.lock()
        try:
            acc1.deposit(100)
        except PermissionError as e:
            print(f"  ✗ Error caught: {e}")
        acc1.unlock()
        acc1.deposit(100, "After unlock")

    except ValueError as e:
        print(f"  Error: {e}")


if __name__ == "__main__":
    main()
