import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
import re

from helpers import apology, login_required, lookup, usd


# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    #current user
    user = session["user_id"]

    #display user's current cash balance, and the stocks total value (stock vlaue + cash)
    hardcash = db.execute("SELECT cash FROM users WHERE id = ?", user)[0]["cash"]

    # display the stocks and  number of shares
    # a user can purchase shares on multiple occasions, the get the correct sum of shares we have to GROUP them and then take the sum of the shares of the same stock
    stockinfo = db.execute("SELECT name, symbol, price, SUM(shares) FROM purchase WHERE user_id = ? GROUP BY symbol", user)

    total = hardcash

    for stock in stockinfo:
        total += stock["price"] * stock["SUM(shares)"]

    return render_template("index.html", stockinfo=stockinfo, hardcash=hardcash, total=total, usd=usd)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # current user
    user = session["user_id"]

    # via post method
    if request.method == "POST":

        # require user input of a symbol
        if not request.form.get("symbol"):
            return apology("field cannot be blank")

        # if symbol doesn't exist
        symbol = request.form.get("symbol")

        validsymbol = lookup(symbol)

        if not validsymbol:
            return apology("symbol doesn't exist")

        # Require that a user input a number of shares
        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("share amount must be positive integer")

        if shares <= 0:
            return apology("number of shares cannot be zero or less")

        # name of the queried symbol
        name = validsymbol["name"]

        # price of the queried symbol
        price = validsymbol["price"]

        # the total cost of the 'x amount of shares' purchased to be substracted from the cash the user has stored in the db
        total_cost = price * shares

        # get at the amount of cash the user has, in order to get at just the integer value, return the first row [0] and the value for ["cash"]
        user_cash = db.execute("SELECT cash FROM users WHERE id = ?", user)[0]["cash"]

        #updated user's cash
        total = user_cash - total_cost

        # if user lacks the funds to make the purchase, render apology
        if user_cash < total_cost:
            return apology("no sufficient funds", 400)

        # else, subtract funds and update DB in the 'users' and the newly made 'purchase' table
        else:
            db.execute("UPDATE users SET cash = ? WHERE id = ?", total, user)
            db.execute("INSERT INTO purchase (user_id, name, symbol, price, shares, type) VALUES (?, ?, ?, ?, ?, ?)", user, name, symbol, price, shares, "purchase")

        # submit via post and return to index
        return redirect("/")

    else:
        dosh = db.execute("SELECT cash FROM users WHERE id = ?", user)

        return render_template("buy.html", dosh = dosh, usd=usd)


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    #current user
    user = session["user_id"]

    db.execute("SELECT * FROM purchase WHERE user_id = ?", user)

    #show the user's stock history (including stock’s symbol, the (purchase or sale) price, the number of shares bought or sold, and the date and time at which the transaction occurred)
    stockhistory = db.execute("SELECT symbol, Type, price, shares, time FROM purchase WHERE user_id = ?", user)

    return render_template("history.html", stockhistory=stockhistory, usd=usd)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""
    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password")

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""
    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    #with method POST
    if request.method == "POST":
        #require user stock symbol input
        if not request.form.get("symbol"):
            return apology("must provide a stock")

        #assign variable to use with "lookup-function"
        symbol = request.form.get("symbol")

        validsymbol = lookup(symbol)

        if not validsymbol:
            return apology("must provide an existing symbol")

        quoted = validsymbol

        #redirect to answer
        return render_template("quoted.html", quoted=quoted, usd=usd)

    # When a user visits /quote via GET, render template /quote,
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    #if method = POST, user filled out a form
    if request.method == "POST":

        #query database
        check = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        #ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        #make sure the username doesn't exist already
        elif len(check) == 1:
            return apology("invalid username and/or password")

        #ensure password given
        elif not request.form.get("password"):
            return apology("must provide password")

        #password must match confirmation
        elif not request.form.get("password") == request.form.get("confirmation"):
            return apology("passwords do not match")

        #username variable to add to db
        username = request.form.get("username")

        #password variable
        password = request.form.get("password")

        #ensure the password meets certain qualities
        if not re.search("[a-z]", password):
            return apology("Password must contain a lower- and uppercase letter, a number and a symbol")

        if not re.search("[A-Z]", password):
            return apology("Password must contain a lower- and uppercase letter, a number and a symbol")

        if not re.search("[0-9]", password):
            return apology("Password must contain a lower- and uppercase letter, a number and a symbol")

        if not re.search("[!@#$%^&*]", password):
            return apology("Password must contain a lower- and uppercase letter, a number and a symbol")

        #hash the password
        hash = generate_password_hash(password)

        #INSERT the new user into users (db)'
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hash)

        #login current user
        # session["user_id"]

        #submit the user’s input via POST to /register.
        return redirect("/")

    else:
        # if method = GET
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    #current user
    user = session["user_id"]

    if request.method == "POST":

        symbol = request.form.get("symbol")

        usershares = db.execute("SELECT SUM(shares) FROM purchase WHERE user_id = ? AND symbol = ? GROUP BY symbol", user, symbol)[0]["SUM(shares)"]

        # user must select a symbol to sell when pressing the 'sell' button
        if not request.form.get("symbol"):
            return apology("field cannot be blank")

        # if the user wants to sell stocks, it must be a positive amount, but it can't be more than he currently owns
        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("share amount must be positive integer")

        if shares <= 0:
            return apology("cannot sell 0 or less shares")

        if usershares < shares:
            return apology("cannot sell more shares than you own")

        validsymbol = lookup(symbol)

        #current price of the stock
        price = validsymbol["price"]

        name = validsymbol["name"]

        #amount the user stands to make with the sale of the stocks
        gains = price * shares

        user_cash = db.execute("SELECT cash FROM users WHERE id = ?", user)[0]["cash"]

        #write new total after user sells his stock
        total = user_cash + gains

        db.execute("UPDATE users SET cash = ? WHERE id = ?", total, user)

        #substract the sold shares from the database
        db.execute("INSERT INTO purchase (user_id, name, shares, price, symbol, type) VALUES (?, ?, ?, ?, ?, ?)", user, name, -shares, price, symbol, "sale")

        # submit via post and return to index
        return redirect("/")

    else:
        #show form to sell keys when using the "GET" method
        #current stocks the user is able to sell
        stocksforsale = db.execute("SELECT symbol FROM purchase WHERE user_id = ? GROUP BY symbol", user)

        return render_template("sell.html", stocksforsale=stocksforsale)




