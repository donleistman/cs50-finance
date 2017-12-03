from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    cash = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])
    cash = round(cash[0]["cash"], 2)
    rows = db.execute("SELECT symbol, SUM(num_shares) FROM transactions WHERE user_id = :user_id GROUP BY symbol", user_id=session["user_id"])
    rows2 = []
    for row in rows:
        if row["SUM(num_shares)"] != 0:
            rows2.append(row)
    stock_total = 0
    for row in rows2:
        stock = lookup(row["symbol"])
        row["current_price"] = stock["price"]
        row["total"] = row['SUM(num_shares)'] * row["current_price"]
        stock_total += row["total"]
    return render_template("index.html", rows=rows2, stock_total=stock_total, cash=cash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")
    else:
        symbol = request.form.get("symbol")
        num_shares = int(request.form.get("num_shares"))
        if not symbol:
            return apology("Missing stock symbol!")
        elif not num_shares:
            return apology("Missing number of shares!")
        else:
            stock = lookup(symbol)
            price = float(stock["price"])
            rows = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])
            cash = rows[0]["cash"]
            if (price * num_shares) > cash:
                return apology("You don't have enough cash!")
            else:
                buy_stock = db.execute("INSERT INTO transactions (user_id, symbol, num_shares, price) VALUES (:user_id, :symbol, :num_shares, :price)", user_id=session["user_id"], symbol=symbol, num_shares=num_shares, price=price)
                if not buy_stock:
                    return apology("Buying stock query failed")
                spend_cash = db.execute("UPDATE users SET cash = cash - :cost WHERE id = :user_id", cost=price*num_shares, user_id=session["user_id"])
                if not spend_cash:
                    return apology("Deducting cash query failed")
                return redirect("/")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    rows = db.execute("SELECT symbol, num_shares, price, timestamp FROM transactions WHERE user_id = :user_id", user_id=session["user_id"])
    for transaction in rows:
        transaction["total"] = transaction["num_shares"] * transaction["price"]
        if transaction["num_shares"] > 0:
            transaction["type"] = "Buy"
        else:
            transaction["type"] = "Sell"
    return render_template("history.html", rows=rows)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

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
    if request.method == "GET":
        return render_template("quote.html")
    else:
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Missing stock symbol!")
        else:
            stock = lookup(symbol)
            return render_template("quote_result.html", stock=stock)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # set variables
    username = request.form.get("username")
    password = request.form.get("password")
    if request.method == "GET":
        return render_template("register.html")
    else:
        if not request.form.get("username"):
            return apology("Missing username!")
        elif password == request.form.get("confirmation"):
            # hash the password
            hash = generate_password_hash(password)
            # add user to database, checking to make sure they are not already registered
            success = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username=username, hash=hash)
            if not success:
                return apology("Username already exists")
            # log them in
            rows = db.execute("SELECT id FROM users WHERE username = :username", username=username)
            session["user_id"] = rows[0]["id"]
            return redirect("/")
        else:
            return apology("Passwords do not match!")




@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":
        rows = db.execute("SELECT symbol, SUM(num_shares) FROM transactions WHERE user_id = :user_id GROUP BY symbol", user_id=session["user_id"])
        stocks = []
        for row in rows:
            if row["SUM(num_shares)"] != 0:
                stocks.append(row)
        return render_template("sell.html", stocks=stocks)
    else:
        symbol = request.form.get("symbol")
        num_shares = int(request.form.get("num_shares"))
        if not symbol:
            return apology("Missing stock symbol!")
        elif not num_shares:
            return apology("Missing number of shares!")
        else:
            stock = lookup(symbol)
            price = float(stock["price"])
            num_shares = 0 - num_shares
            sell_stock = db.execute("INSERT INTO transactions (user_id, symbol, num_shares, price) VALUES (:user_id, :symbol, :num_shares, :price)", user_id=session["user_id"], symbol=symbol, num_shares=num_shares, price=price)
            if not sell_stock:
                return apology("Buying stock query failed")
            get_cash = db.execute("UPDATE users SET cash = cash - :cost WHERE id = :user_id", cost=price*num_shares, user_id=session["user_id"])
            if not get_cash:
                return apology("Deducting cash query failed")
            return redirect("/")

        return render_template("sell.html")



def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)