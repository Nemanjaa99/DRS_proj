import hashlib
import multiprocessing
import threading
import time

import requests
from flask import Flask, request, render_template, session, redirect
from flask_socketio import SocketIO
from flask_session import Session

app = Flask(__name__)
socketio = SocketIO(app, async_type=None)
app.config["SESSION_PERMANENT"] = False
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)


clients = {}

url = "http://127.0.0.1:5000"

api_key = hashlib.md5(b'flaskApp').hexdigest()


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        data = {
            "email": request.form["email"],
            "password": request.form["password"],
            "api_key": api_key
        }
        response = requests.post(url + "/login", data=data).json()
        if response['status'] == 200:
            session['uid'] = response['user']['uid']
            session['email'] = response['user']['email']
            session['message'] = response['message']
            return redirect("/")
        else:
            session['error'] = response['message']
            return redirect("/login")

    if request.method == "GET":
        return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        data = {
            "fname": request.form["fname"],
            "lname": request.form["lname"],
            "email": request.form["email"],
            "password": request.form["password"],
            "address": request.form["address"],
            "city": request.form["city"],
            "country": request.form["country"],
            "phone": request.form['phone'],
            "api_key": api_key
        }
        response = requests.post(url + "/register", data=data).json()
        if response['status'] == 200:
            session['uid'] = response['uid']
            session['email'] = response['email']
            return redirect("/")
        else:
            session['error'] = response['message']
            return redirect("/")
    if request.method == "GET":
        return render_template("register.html")


@app.route("/")
def index():
    if not UserLoggedIn():
        return redirect("/login")
    response = requests.get(url + "/").json()
    if response['status'] == 200:
        return render_template("index.html", currencies=response['currencies'])
    else:
        return redirect("/")


@app.route("/logout")
def logout():
    session['uid'] = None
    session['email'] = None
    return redirect("/")


@app.route("/account", methods=["GET", "POST"])
def account():
    if not UserLoggedIn():
        return redirect("/login")
    if request.method == "GET":
        response = requests.get(url + "/account", params={"user_id": session['uid'], "api_key": api_key}).json()
        if response["status"] == 200:
            user = response['user']
            payment_info = response["pinfo"]
            return render_template("account.html", account=user, payment_info=payment_info)
        else:
            session['error'] = response['message']
            return redirect("/")
    if request.method == "POST":
        data = {
            "user_id": session['uid'],
            "email": session['email'],
            "fname": request.form['fname'],
            "lname": request.form["lname"],
            "city": request.form['city'],
            "address": request.form["address"],
            "country": request.form["country"],
            "phone": request.form["phone"],
            "api_key": api_key
        }
        response = requests.post(url + '/account', data=data).json()
        if response['status'] == 200:
            session['message'] = response['message']
            return redirect("/account")
        else:
            session['error'] = response['message']
            return redirect("/account")


@app.route("/paymentInformation", methods=["POST"])
def paymentInformation():
    if not UserLoggedIn():
        return redirect("/login")
    data = {
        "cholder": request.form["cholder"],
        "cnumber": request.form["cnumber"],
        "month": request.form['month'],
        "year": request.form['year'],
        "cvc": request.form['cvc'],
        'user_id': session['uid'],
        "api_key": api_key
    }
    response = requests.post(url + "/paymentInformation", data=data).json()
    if response['status'] == 200:
        session['message'] = response['message']
    else:
        session['error'] = response['message']
    return redirect("/account")


@app.route("/payment", methods=["POST"])
def payment():
    if not UserLoggedIn():
        return redirect("/login")
    data = {
        "user_id": session['uid'],
        "amount": request.form["ammount"],
        "api_key": api_key
    }
    response = requests.post(url + "/payment", data=data).json()
    if response['status'] == 200:
        session['message'] = response['message']
    else:
        session['error'] = response['message']
    return redirect("account")


@app.route("/transactions")
def transactions():
    if not UserLoggedIn():
        return redirect("/login")
    response = requests.get(url + "/transactions", params={"user_id": session['uid'], "api_key": api_key}).json()
    if response['status'] == 200:
        sent = response['sent']
        received = response['received']
        currencies = response['currencies']
        return render_template("transactions.html", sent=sent, received=received, currencies=currencies)
    else:
        session['error'] = response['message']
        return redirect("/")


@app.route("/wallets")
def wallets():
    if not UserLoggedIn():
        return redirect("/login")
    user_id = session['uid']
    response = requests.get(url + "/wallets", data={"user_id": user_id, "api_key": api_key}).json()
    if response['status'] == 200:
        wallets = response['wallets']
        return render_template("wallets.html", wallets=wallets)
    else:
        session['error'] = response['message']
        return redirect("/")


@app.route("/cryptoWithdrawal", methods=["POST"])
def withdraw():
    if not UserLoggedIn():
        return redirect("/login")
    quantity = request.form['quantity']
    currency_id = request.form['currency_id']
    data = {
        "user_id": session['uid'],
        "quantity": quantity,
        "currency_id": currency_id,
        "api_key": api_key
    }
    response = requests.post(url + "/cryptoWithdrawal", data=data).json()
    return response


@app.route("/getCryptoDetails")
def getCryptoDetails():
    return requests.get(url + "/getCryptoDetails", params={"id": request.args['id']}).json()


@app.route("/getUserBalance")
def getUserBalance():
    return requests.get(url + "/getUserBalance", params={"user_id": session['uid']}).json()


@app.route("/prepareTransaction", methods=["POST"])
def prepareTrans():
    if not UserLoggedIn():
        return redirect("/login")
    data = {
        "receiver": request.form['receiver'],
        "sender": session['uid'],
        "currency_id": request.form['currency_id'],
        "currency_quantity": request.form['currency_quantity'],
        "api_key": api_key
    }
    return requests.post(url + "/prepareTransaction", data=data).json()


@app.route("/initiateTransaction", methods=["POST"])
def initiateTransaction():
    if not UserLoggedIn():
        return redirect("/login")
    data = {
        "sender_id": request.form['sender_id'],
        "receiver_id": request.form['receiver_id'],
        "currency": request.form['currency'],
        "quantity": request.form['quantity'],
        "api_key": api_key
    }
    response = requests.post(url + "/initiateTransaction", data=data).json()
    print(response)
    if response['status'] == 200:
        socketio.start_background_task(handleTransaction, response['transaction'], request.form['receiver_id'])
    return response


def handleTransaction(transactionData, receiver_id):
    print("HADNLING")
    print(transactionData['transaction'])
    transactionData['transaction']['api_key'] = api_key
    response = requests.post(url + "/handleTransaction", data=transactionData['transaction']).json()
    print("RESPONSE")
    print(response)
    if response['status'] == 200:
        try:
            socketio.emit("newTransaction", {"data": transactionData}, room=clients[int(receiver_id)])
        except Exception as err:
            print("User not online to notify him of the transaction")
        #promeniti u 300 za cekanje od 5 minuta
        socketio.sleep(10)
        res = requests.post(url + "/processTransaction",
                            data={"transaction_id": response['transaction_id'], "api_key": api_key}).json()
        if res['status'] == 200:
            try:
                socketio.emit("processedTransaction", {"data": res}, room=clients[int(receiver_id)])
            except Exception as err:
                print("User not online to notify him of the transaction")
        else:
            print(res)
    else:
        return response


@socketio.on("connect")
def memorizeUser():
    try:
        clients[session['uid']] = request.sid
        print("User memorized")

    except Exception as err:
        print("Error while memorizing the user. Error text: " + str(err))


@socketio.on("disconnect")
def removeUser():
    try:
        clients.pop(session['uid'])
    except Exception as err:
        print("Error while removing the user from clientlist. Error text: " + str(err))


cryptoData = []
cryptoData = requests.get(url + "/getCryptoRates").json()


@socketio.on('getCryptoData')
def GetCryptoData(data):
    threadName = "cryptoRatesThread" + str(session['uid'])
    threadExists = False
    for thread in threading.enumerate():
        if thread.name == threadName:
            print("Thread not started because it is already running")
            threadExists = True
    if not threadExists:
        pr = threading.Thread(target=cryptoDataThread, name=threadName)
        pr.start()
    global cryptoData
    socketio.emit("receiveCryptoData", {"data": cryptoData})


def cryptoDataThread():
    global cryptoData
    print(cryptoData)
    while True:
        cryptoData = requests.get(url + "/getCryptoRates").json()
        socketio.emit("receiveCryptoData", {"data": cryptoData})
        time.sleep(60)


def UserLoggedIn():
    if 'uid' not in session or session['uid'] is None:
        return False
    return True


if __name__ == '__main__':
    socketio.run(app, debug=True, port=5001)
