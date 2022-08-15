import random
import time

from flask import session
from flask_session import Session
import requests
import sqlite3
from Crypto.Hash import keccak


class Engine:
    @staticmethod
    def InitSession():
        session["uid"] = None
        session['email'] = None

    @staticmethod
    def UserLoggedIn():
        if session["uid"] is not None:
            return True
        return False

    @staticmethod
    def Logout():
        session['uid'] = None
        session['email'] = None

    @staticmethod
    def GetConnection():
        return sqlite3.connect("database.db")

    @staticmethod
    def GetUser(id):
        conn = Engine.GetConnection()
        curr = conn.cursor()
        curr.execute("SELECT * from users where id = ? or email = ?", (id, id))
        user = curr.fetchone()
        return user

    @staticmethod
    def UpdateUser(fname, lname, address, city, country, phone, id):
        conn = Engine.GetConnection()
        curr = conn.cursor()
        curr.execute("UPDATE users set fname = ?, lname = ?, address = ?, city = ?, country = ?,phone = ? WHERE id = ?",
                     (fname, lname, address, city, country, phone, id))
        conn.commit()

    @staticmethod
    def GetUserPaymentInformation(id):
        conn = Engine.GetConnection()
        curr = conn.cursor()
        curr.execute("SELECT cholder, cnumber,valid_through,cvc,balance FROM users where id = ?", (id,))
        pinfo = curr.fetchone()
        if pinfo[0] is None:
            return None
        else:
            return pinfo

    @staticmethod
    def SetPaymentInformation(cholder, cnumber, valid_date, cvc, id):
        conn = Engine.GetConnection()
        curr = conn.cursor()
        curr.execute("UPDATE users set cholder = ?, cnumber = ?, valid_through = ?,cvc = ? where id = ?",
                     (cholder, cnumber, valid_date, cvc, id))
        try:
            conn.commit()
            conn.close()
            return True
        except Exception as err:
            conn.rollback()
            conn.close()
            return False

    @staticmethod
    def ValidateRequest(req):
        for item in req:
            if len(req) == 0 or req == " ":
                return False
        return True

    @staticmethod
    def AddMoney(ammount, id):
        conn = Engine.GetConnection()
        curr = conn.cursor()
        curr.execute("UPDATE users set balance = balance + ? where id = ?", (ammount, id))
        try:
            conn.commit()
            return True
        except Exception as err:
            conn.rollback()
            print(str(err))
            return False

    @staticmethod
    def GetCurrencies():
        conn = Engine.GetConnection()
        curr = conn.cursor()
        curr.execute("SELECT * from currencies")
        currencies = curr.fetchall()
        return currencies

    @staticmethod
    def GetCurrency(id):
        conn = Engine.GetConnection()
        curr = conn.cursor()
        curr.execute("SELECT * from currencies where id = ? or short_name = ? or name = ?", (id, id, id))
        currencies = curr.fetchone()
        return currencies

    @staticmethod
    def GetCurrencyPricing():
        currencies = Engine.GetCurrencies()
        print(currencies)
        currency_data = []
        for currency in currencies:
            cdata = {
                "name": currency[1],
                "short_name": currency[2],
                "price": 0,
            }
            price_usd = requests.get("https://api.coinbase.com/v2/prices/" + cdata['short_name'] + "-USD/buy").json()
            cdata['price'] = price_usd['data']['amount']
            currency_data.append(cdata)
        return currency_data

    @staticmethod
    def GetSpecificCurrencyPricing(id):
        print(id)
        currency = Engine.GetCurrency(id)
        print(currency)
        cdata = {
            "name": currency[1],
            "short_name": currency[2],
            "price": 0
        }
        price_usd = requests.get("https://api.coinbase.com/v2/prices/" + cdata['short_name'] + "-USD/buy").json()
        cdata['price'] = price_usd['data']['amount']
        print(cdata)
        return cdata

    @staticmethod
    def GetUserBalance(uid):
        account_info = Engine.GetUserPaymentInformation(uid)
        if account_info is not None:
            return {'balance': account_info[4]}
        return {'balance': 0}

    @staticmethod
    def GetUserEmail(uid):
        user = Engine.GetUser(uid)
        if user is None:
            return None
        return user[3]

    @staticmethod
    def PrepareTransaction(sender_id, receiver_id, currency, quantity):
        sender_email = Engine.GetUserEmail(sender_id)
        receiver_email = Engine.GetUserEmail(receiver_id)
        response = {}
        if sender_email is None:
            response = {
                'error': 'Posiljalac ne postoji',
                'status': 500
            }
            return response
        if receiver_email is None:
            response = {
                'error': 'Primalac ne postoji',
                'status': 500
            }
            return response
        data = sender_email + receiver_email + currency + quantity + str(random.randint(1, 512))
        keccak_hash = keccak.new(digest_bits=256)
        keccak_hash.update(str.encode(data))
        hash_id = keccak_hash.hexdigest()
        response = {
            'status': 200,
            'transaction': {
                'hash_id': hash_id,
                'sender_id': sender_id,
                'receiver_id': receiver_id,
                'currency_id': Engine.GetCurrency(currency)[0],
                'quantity': quantity
            }
        }
        return response

    @staticmethod
    def StoreTransaction(transactionData):
        conn = Engine.GetConnection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT into transactions(hash_id,sender_id,recevier_id,currency_id,quantity) VALUES (?,?,?,?,?)", (
                transactionData["hash_id"], transactionData["sender_id"], transactionData["receiver_id"],
                transactionData["currency_id"], transactionData["quantity"]))
        conn.commit()
        return cursor.lastrowid

    @staticmethod
    def GetTransactionDetails(tid):
        conn = Engine.GetConnection()
        cursor = conn.cursor()
        cursor.execute("SELECT * from transactions where id = ?", (tid,))
        unparsed_transaction = cursor.fetchone()
        transaction = {
            "hash_id": unparsed_transaction[1],
            'sender_id': unparsed_transaction[2],
            'receiver_id': unparsed_transaction[3],
            'currency_id': unparsed_transaction[4],
            'quantity': unparsed_transaction[5],
            'status': unparsed_transaction[6]
        }
        return transaction

    @staticmethod
    def ProcessTransaction(tid):
        conn = Engine.GetConnection()
        cursor = conn.cursor()
        transaction = Engine.GetTransactionDetails(tid)
        userbal = Engine.GetUserBalance(transaction['sender_id'])['balance']
        print("currval")
        print(Engine.GetSpecificCurrencyPricing(transaction['currency_id'])['price'])
        transactionValue = float(transaction['quantity']) * float(
            Engine.GetSpecificCurrencyPricing(transaction['currency_id'])[
                'price'])
        if userbal < transactionValue:
            cursor.execute("UPDATE transactions set status = 'Odbijena' where id = ?", (tid,))
            conn.commit()
            return False
        else:
            cursor.execute("UPDATE transactions set status = 'Odobrena' where id = ?", (tid,))
            conn.commit()
            Engine.HandleWallets(transaction['receiver_id'], transaction['currency_id'], transaction['quantity'])
            cursor.execute("UPDATE users set balance = balance - ? where id = ?",
                           (transactionValue, transaction['sender_id']))
            conn.commit()
            return True

    @staticmethod
    def GetCryptoWallet(uid, cid):
        conn = Engine.GetConnection()
        cursor = conn.cursor()
        cursor.execute("SELECT * from crypto_wallets where user_id = ? and currency_id = ?", (uid, cid))
        wallet = cursor.fetchone()
        if wallet is not None:
            refined_wallet = {
                'id': wallet[0],
                'user_id': wallet[1],
                'currency_id': wallet[2],
                'balance': wallet[3]
            }
            return refined_wallet
        return None

    @staticmethod
    def HandleWallets(uid, cid, quantity):
        conn = Engine.GetConnection()
        cursor = conn.cursor()
        if Engine.GetCryptoWallet(uid, cid) is None:
            cursor.execute("INSERT into crypto_wallets(user_id, currency_id,balance) VALUES (?,?,?)",
                           (uid, cid, quantity))
            conn.commit()
        else:
            cursor.execute("UPDATE crypto_wallets set balance = balance + ? where user_id = ? and currency_id = ?",
                           (quantity, uid, cid))
            conn.commit()

    @staticmethod
    def GetReceivedTransactions(uid):
        conn = Engine.GetConnection()
        curr = conn.cursor()
        curr.execute("SELECT * from transactions where recevier_id = ?", (uid,))
        transactions = curr.fetchall()
        refined_transactions = []
        for transaction in transactions:
            refined_transaction = {
                'id': transaction[0],
                "hash_id": transaction[1],
                'sender_id': transaction[2],
                'receiver_id': transaction[3],
                'currency_id': transaction[4],
                'currency': Engine.GetCurrency(transaction[4])[1],
                'quantity': transaction[5],
                'status': transaction[6],
                'created_at': transaction[7]
            }
            refined_transactions.append(refined_transaction)
        return refined_transactions

    @staticmethod
    def GetSentTransactions(uid):
        conn = Engine.GetConnection()
        curr = conn.cursor()
        curr.execute("SELECT * from transactions where sender_id = ?", (uid,))
        transactions = curr.fetchall()
        refined_transactions = []
        for transaction in transactions:
            refined_transaction = {
                'id': transaction[0],
                "hash_id": transaction[1],
                'sender_id': transaction[2],
                'receiver_id': transaction[3],
                'currency_id': transaction[4],
                'currency': Engine.GetCurrency(transaction[4])[1],
                'quantity': transaction[5],
                'status': transaction[6],
                'created_at': transaction[7]

            }
            refined_transactions.append(refined_transaction)
        return refined_transactions

    @staticmethod
    def CryptoToDollars(currency, amount):
        cryptoPrice = Engine.GetSpecificCurrencyPricing(currency)
        return float(cryptoPrice['price']) * float(amount)

    @staticmethod
    def GetIDFromEmail(email):
        user = Engine.GetUser(email)
        if user is not None:
            return user[0]
        else:
            return None

    @staticmethod
    def GetUserWallets(uid):
        conn = Engine.GetConnection()
        cursor = conn.cursor()
        cursor.execute("SELECT * from crypto_wallets where user_id = ?", (uid,))
        wallets = cursor.fetchall()
        refactored_wallets = []
        for wallet in wallets:
            currency = Engine.GetCurrency(wallet[2])
            rw = {
                'currency_id': currency[0],
                'currency': currency[1],
                'quantity': wallet[3]
            }
            refactored_wallets.append(rw)
        return refactored_wallets

    @staticmethod
    def GetWalletBalance(uid, cid):
        conn = Engine.GetConnection()
        curr = conn.cursor()
        curr.execute("SELECT balance from crypto_wallets where user_id = ? and currency_id = ?", (uid, cid))
        wallet = curr.fetchone()
        return float(wallet[0])

    @staticmethod
    def WithdrawCurrency(uid, cid, quantity):
        conn = Engine.GetConnection()
        cursor = conn.cursor()
        availableAmmount = Engine.GetWalletBalance(uid, cid)
        if availableAmmount < float(quantity):
            return False
        else:
            cryptoPrice = Engine.GetSpecificCurrencyPricing(cid)['price']
            addToAccount = float(cryptoPrice) * float(quantity)
            if Engine.GetUserPaymentInformation(uid) == None:
                return False
            else:
                cursor.execute("UPDATE crypto_wallets set balance = balance - ? where user_id = ? and currency_id = ?",
                               (quantity, uid, cid))
                conn.commit()
                cursor.execute("UPDATE users set balance = balance + ? where id = ?", (addToAccount, uid))
                conn.commit()
                return True
