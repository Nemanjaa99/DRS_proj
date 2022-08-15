import datetime
import json
import threading
import time

from flask import Flask
from flask import render_template, request
from flask import redirect
from flask import session
from flask_session import Session
from flask_socketio import SocketIO, emit, disconnect
from threading import Lock
from Engine import Engine
import hashlib
import re
from json import JSONDecoder, JSONEncoder

app = Flask(__name__)
socketio = SocketIO(app, async_type=None)
app.config["SESSION_PERMANENT"] = False
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)
thread = None
thread_lock = Lock()

api_key = hashlib.md5(b'flaskApp').hexdigest()


def validKey(request):
    if 'api_key' not in request.form:
        return {
            "status": 500,
            "message": "API kljuc nedostaje"
        }
    elif api_key != request.form['api_key']:
        return {
            "status": 500,
            "message": "API kljuc nije ispravan"
        }
    else:
        return True


loggedInUsers = {}

cryptoRates = []


# def getCryptoRates():
#
#     # while True:
#     #     cryptoRates = Engine.GetCurrencyPricing()
#     #     socketio.emit("currency_data", {'data': cryptoRates})
#     #     print('Emitting')
#     #     time.sleep(60)
@app.route("/getCryptoRates")
def getCRates():
    response = {}
    try:
        response = {
            "rates": Engine.GetCurrencyPricing(),
            "status": 200
        }
    except Exception as err:
        response = {
            "status": 500,
            "message": str(err)
        }
    finally:
        return response


@app.route('/')
def index():
    currencies = Engine.GetCurrencies()
    response = {
        "status": 200,
        "currencies": currencies
    }
    return response


@app.route('/login', methods=["POST"])
def login():
    if not validKey(request):
        return validKey(request)
    email = request.form['email']
    password = hashlib.md5(request.form['password'].encode()).hexdigest()
    conn = Engine.GetConnection()
    curr = conn.cursor()
    curr.execute("SELECT * FROM users WHERE email = ? AND password = ?", (email, password))
    user = curr.fetchone()
    response = {}
    if user is not None:
        uid = user[0]
        email = user[3]
        response['status'] = 200
        userDict = {
            "uid": uid,
            "email": email
        }
        response["user"] = dict(userDict)
        response['message'] = "Uspesno prijavljivanje. Dobrodosli!"
        return response
    else:
        response['status'] = 500
        response['user'] = {}
        response['message'] = "Greska prilikom prijavljivanja. Proverite unete podatke i pokusajte opet"
        return response


@app.route("/register", methods=["POST"])
def register():
    if not validKey(request):
        return validKey(request)
    if request.method == 'POST':
        response = {}
        try:
            fname = request.form['fname']
            lname = request.form['lname']
            email = request.form['email']
            password = hashlib.md5(request.form['password'].encode()).hexdigest()
            address = request.form['address']
            city = request.form['city']
            phone = request.form['phone']
            country = request.form['country']
            print(fname, lname, email, password, address, city, country)
            conn = Engine.GetConnection()
            curr = conn.cursor()
            curr.execute(
                "INSERT into users(fname,lname,email,password,address,city,country,phone) VALUES (?,?,?,?,?,?,?,?)",
                (fname, lname, email, password, address, city, country, phone))
            conn.commit()
            session['uid'] = curr.lastrowid()
            session['email'] = email
        except Exception as err:
            response = {
                "status": 500,
                "message": "Doslo je do greske prilikom registrovanja korisnika. Tekst greske: " + str(err)
            }
        finally:
            return response


@app.route('/account', methods=["GET", "POST"])
def account():
    if not validKey(request):
        return validKey(request)
    response = {}
    if request.method == "GET":
        try:
            user = Engine.GetUser(request.args['user_id'])
            pinfo = Engine.GetUserPaymentInformation(request.args['user_id'])
            print(pinfo)
            response = {
                "status": 200,
                "user": user,
                "pinfo": pinfo
            }
        except Exception as err:
            response = {
                "status": 500,
                "message": "Greska prilikom povlacenja podataka o nalogu. Tekst greske: " + str(err)
            }
        finally:
            return response
    if request.method == "POST":
        uid = request.form['user_id']
        fname = request.form['fname']
        lname = request.form['lname']
        city = request.form['city']
        address = request.form['address']
        country = request.form['country']
        phone = request.form["phone"]
        user = Engine.GetUser(uid)
        if user is None:
            response = {
                "status": 500,
                "message": "Korisnik sa datim podacima ne potoji u sistemu"
            }
        else:
            if user[3] != request.form['email']:
                response = {
                    "status": 500,
                    "message": "Nemate ovlascenje za izmenu ovog naloga"
                }
            else:
                Engine.UpdateUser(fname, lname, address, city, country, phone, uid)
                response = {
                    "status": 200,
                    "message": "Uspesno izmenjen nalog"
                }
        return response


@app.route("/paymentInformation", methods=["POST"])
def paymentinformation():
    if not validKey(request):
        return validKey(request)
    try:
        cholder = request.form["cholder"]
        cnumber = request.form["cnumber"]
        vmonth = int(request.form['month'])
        vyear = int("20" + request.form['year'])
        cvc = request.form['cvc']
        user_id = request.form['user_id']
        if Engine.ValidateRequest(request.form) is False:
            return {
                "status": 500,
                "message": "Popunite sve podatke"
            }
        # regex pattern for validating the card number
        pattern = r"^\d{4}[ ]\d{4}[ ]\d{4}[ ]\d{4}$"
        if not re.fullmatch(pattern, cnumber):
            return {
                "status": 500,
                "message": "Broj kartice nije validan"
            }
        else:
            valid_date = datetime.datetime(vyear, vmonth, 1)
            if datetime.datetime.now() > valid_date:
                return {
                    "status": 500,
                    "message": "Kartica nije validna"
                }
            else:
                valid_date = datetime.datetime(vyear, vmonth, 1)
                if Engine.SetPaymentInformation(cholder, cnumber, valid_date.strftime("%m/%y"), cvc,
                                                user_id) is True:
                    return {
                        "status": 200,
                        "message": "Uspesno dodat nacin placanja"
                    }
                else:
                    return {
                        "status": 500,
                        "message": "Doslo je do greske prilikom dodavanja nacina placanja"
                    }
    except Exception as err:
        print(str(err))
        return {
            "status": 500,
            "message": "Doslo je do greske. Tekst greske: " + str(err)
        }


@app.route("/payment", methods=["POST"])
def payment():
    if not validKey(request):
        return validKey(request)
    try:
        user_id = request.form['user_id']
        ammount = request.form['amount']
        Engine.AddMoney(ammount, user_id)
        return {
            "status": 200,
            "message": "Uspesno dodato $" + str(ammount) + ".00 na nalog."
        }

    except Exception as err:
        return {
            "status": 500,
            "message": "Doslo je do greske prilikom izvrsenja uplate. Greska: " + str(err)
        }


@app.route("/currencies")
def currencies():
    currencies = Engine.GetCurrencyPricing()
    print(currencies)
    return json.dumps(currencies)


@app.route("/getCryptoDetails")
def getCryptoDetails():
    cid = request.args['id']
    pricing = Engine.GetSpecificCurrencyPricing(cid)
    print(pricing)
    return pricing


@app.route("/getUserBalance")
def getUserBalance():
    if not validKey(request):
        return validKey(request)
    return Engine.GetUserBalance(request.args["user_id"])


@app.route('/initiateTransaction', methods=["POST"])
def processTransaction():
    if not validKey(request):
        return validKey(request)
    try:
        sender_id = request.form['sender_id']
        receiver_id = request.form['receiver_id']
        currency = request.form['currency']
        quantity = request.form['quantity']
        transactionData = Engine.PrepareTransaction(sender_id, receiver_id, currency, quantity)
        return {
            "status": 200,
            "transaction": transactionData
        }
    except Exception as err:
        return {
            "status": 500,
            "message": str(err)
        }
    # if 'error' not in transactionData:
    #     threading.Thread(target=initiateTransaction, args=(transactionData["transaction"],)).start()
    #     return 'process finished'
    # else:
    #     return transactionData


@app.route("/handleTransaction", methods=["POST"])
def handleTransaction():
    if not validKey(request):
        return validKey(request)
    try:
        transaction = {
            "hash_id": request.form['hash_id'],
            "sender_id": request.form["sender_id"],
            "receiver_id": request.form['receiver_id'],
            "quantity": request.form['quantity'],
            "currency_id": request.form['currency_id']
        }
        print(transaction)
        tid = storeTransaction(transaction)
        return {
            "status": 200,
            "transaction_id": tid
        }
    except Exception as err:
        return {
            "status": 500,
            "message": str(err)
        }


def storeTransaction(transData):
    # code to insert the data into the database
    tid = Engine.StoreTransaction(transData)
    return tid
    # inform the user of a new transaction
    # try:
    #     socketio.emit("newTransaction", {'data': transData}, room=loggedInUsers[int(transData['receiver_id'])])
    # except Exception as err:
    #     print(str(err))
    #     print("User not active to notify him of a transaction")
    # # time delay
    # time.sleep(10)
    # print("Sleeping")
    # # process transaction
    # try:
    #     socketio.emit('processedTransaction', {'accepted': result, 'data': transData},
    #                   room=loggedInUsers[int(transData['receiver_id'])])
    #     print("Notifying user")
    # except Exception as err:
    #     print(str(err))
    #     print("User not active to notify him of a transaction result")


@app.route("/processTransaction", methods=["POST"])
def processTrans():
    if not validKey(request):
        return validKey(request)
    try:
        action = Engine.ProcessTransaction(request.form['transaction_id'])
        return {
            "status": 200,
            "accepted": action
        }
    except Exception as err:
        return {
            "status": 500,
            "message": str(err)
        }


@app.route("/transactions")
def getTransactions():
    if not validKey(request):
        return validKey(request)
    try:
        user_id = request.args['user_id']
        receivedTransactions = Engine.GetReceivedTransactions(user_id)
        sentTransactions = Engine.GetSentTransactions(user_id)
        currencies = Engine.GetCurrencies()
        return {
            "status": 200,
            "currencies": currencies,
            "sent": sentTransactions,
            "received": receivedTransactions
        }
    except Exception as err:
        return {
            "status": 500,
            "message": "Greska prilikom pronalazenja transakcija. Tekst greske: " + str(err)
        }


@app.route("/prepareTransaction", methods=["POST"])
def prepareTransaction():
    if not validKey(request):
        return validKey(request)
    print(request.form)
    receiver_email = request.form['receiver']
    sender = request.form['sender']
    currency_id = request.form['currency_id']
    quantity = request.form['currency_quantity']
    response = {}
    if Engine.GetIDFromEmail(receiver_email) == None:
        response = {
            'status': 500,
            'message': "Korisnik sa ovom email adresom ne postoji u sistemu. Transfer se otkazuje"
        }
    else:
        response = {
            'status': 200,
            'message': 'Korisnik pronadjen. Kreiranjem transakcije sa Vaseg naloga ce biti skinuto $' + str(
                float(Engine.GetSpecificCurrencyPricing(
                    currency_id)['price']) * float(
                    quantity)) + " i pretvoreno u odabranu valutu na nalogu drugog korisnika. Potvrdi transakciju?",
            'transaction_data': {
                'sender_id': sender,
                'receiver_id': Engine.GetIDFromEmail(receiver_email),
                'currency': Engine.GetCurrency(currency_id)[2],
                'quantity': quantity
            }
        }
    return response


@app.route("/wallets")
def getWallets():
    if not validKey(request):
        return validKey(request)
    try:
        user_id = request.form['user_id']
        wallets = Engine.GetUserWallets(user_id)
        return {
            "status": 200,
            "wallets": wallets
        }
    except Exception as err:
        return {
            "status": 500,
            "message": "Doslo je do greske prilikom preuzimanja kriptonovcanika. Tekst greske: " + str(err)
        }


@app.route("/cryptoWithdrawal", methods=["POST"])
def cryptoWithdrawal():
    if not validKey(request):
        return validKey(request)
    try:
        cid = request.form['currency_id']
        quantity = request.form['quantity']
        uid = request.form['user_id']
        return {"status": 200, 'success': Engine.WithdrawCurrency(uid, cid, quantity)}
    except Exception as err:
        return {"status": 500, 'message': str(err)}


@socketio.on('connect')
def memorizeUser():
    loggedInUsers[session['uid']] = request.sid
    print('Saved a user')

    # threading.Thread(target=broadCastMessage()).start()


@socketio.on('getCryptoData')
def getCryptoData(msg):
    threadName = "RetreivalThread" + str(session['uid'])
    if not threadExists(threadName):
        rateRetreival = threading.Thread(target=getCryptoRates, name=threadName)
        rateRetreival.start()
    else:
        print("Thread not started because it already exists")
        cryptoRates = Engine.GetCurrencyPricing()
        socketio.emit("currency_data", {'data': cryptoRates})


@socketio.on("connect", namespace="/listen")
def handleListenSocket():
    print("Listening for transactions")


def threadExists(name):
    for th in threading.enumerate():
        if th.name == name:
            return True
    return False


def closeThread(name):
    for th in threading.enumerate():
        if th.name == name:
            print("Thread" + th.name + " stopped")
            th.join()
            return


@socketio.on("disconnect")
def stopBroadCasting():
    print("user disconnected")
    if threadExists("RetrevialThread" + str(session['uid'])):
        print("Thread found, closing now")
        closeThread("RetrevialThread" + str(session['uid']))


if __name__ == '__main__':
    # app.run(FLASK_DEBUG=True)
    socketio.run(app, debug=True, port=5000)
