#!/usr/bin/env python3
import sqlite3, uuid, json, socket
from flask import g, Flask
from flask import session, redirect, url_for, request, render_template, flash
from collections import Counter
import functools
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
import random
import config


#login_manager = LoginManager()

# Borrowed code from
# https://flask.palletsprojects.com/en/1.1.x/patterns/sqlite3/
#

app = Flask(__name__)
# secret key
app.secret_key = b'\x060W}\x10\x03\xcc\xf7$[\xc6H\x88\xa6\x87\x0c'

#login_manager.init_app(app)
login = LoginManager(app)
login.login_view = 'login'

DATABASE = config.DATABASE

@login.user_loader
def load_user(id):
    if id=="alexei":
        return User(id)
    else:
        return None

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# Initialise from a python session
# >>> import app
# >>> app.init_db()
# >>> app.init_data()
def init_db():
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()

# convenience function for queries
def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def init_data():
    # hack to initially populate some values
    with app.app_context():
        db = get_db()
        # clear any existing votes
        db.execute("INSERT INTO polls (poller, pollcode, pollvalues, status) VALUES (?,?,?,?)",
                    ["alexei", "121", "A B C D", 0])
        db.commit()


class User(object):
    def __init__(self, id):
        self.id = id
        
    @property
    def is_active(self):
        return True

    @property
    def is_authenticated(self):
        if self.id is None:
            return False
        else:
            return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return self.id


@app.route('/', methods=('GET', 'POST'))
def index():
    pollcode = None
    error = None

    if 'uid' not in session:
        # Assign a new uuid
        # TODO base it on comp/ip too?
        session['uid'] = uuid.uuid4().hex

    # these override the current poll
    newpollcode = None
    if request.method == 'GET':
        newpollcode = request.args.get('pollcode')
    elif request.method == 'POST':
        newpollcode = request.form['pollcode']
    if newpollcode is not None:
        session['pollcode'] = newpollcode

    if "pollcode" in session:
        # Is the poll still valid?
        pollcode = session["pollcode"]
        poll = query_db("SELECT * FROM polls WHERE pollcode = ?",[pollcode], one=True)
        if poll is None:
            error = "Poll '{}' doesn't exist".format(pollcode)
            del session['pollcode']

        else:
            # Check to see if the user already voted
            vote = None
            uid = session['uid']
            prev_vote =  query_db("SELECT * FROM votes WHERE pollcode = ? AND userid = ?",[pollcode, uid])
            if len(prev_vote)>0:
                vote = prev_vote[0]["choice"]

            labels = poll["pollvalues"].split()
            return render_template("poll.html", pollcode=pollcode, values=labels, vote=vote)

    if error is not None:
        flash(error)
       
    return render_template("choosepoll.html", session=session)

@app.route('/forgetpoll')
def forgetpoll():
    if 'pollcode' in session:
        del session['pollcode']
    return redirect(url_for('index'))

@app.route('/vote', methods=('GET', 'POST'))
def vote():
    error = None
    uid = session['uid']
    pollcode = session['pollcode']
    if request.method == 'GET':
        vote = request.args.get('vote', default=None)

        if pollcode is None or vote is None:
            error = "Missing poll or vote"
        else:
            poll = query_db("SELECT * FROM polls WHERE pollcode = ?",[pollcode], one=True)
            if poll is None:
                error = "Poll '{}' doesn't exist".format(pollcode)
            elif vote not in poll["pollvalues"].split():
                error = "Choice not in current poll"
            else:
                db = get_db()
                # clear any existing votes
                db.execute("DELETE FROM votes WHERE pollcode = ? AND userid = ?", [pollcode, uid])
                db.execute("INSERT INTO votes (userid, pollcode, choice) VALUES (?,?,?)",
                                           [uid, pollcode, vote])
                db.commit()

    if error is not None:
        flash(error)

    return redirect(url_for('index'))



@app.route('/clear')
def clearuid():
    for key in ['uid', 'pollcode']:
        if key in session:
            del session[key]

    flash("Cleared session data")
    return redirect(url_for('index'))

@app.route('/clearvotes/<pollcode>')
def clearvotes(pollcode):
    db = get_db()
    db.execute("DELETE FROM votes WHERE pollcode = ?", [pollcode])
    db.execute("UPDATE polls SET status = 0 WHERE pollcode = ?", [pollcode])
    db.commit()

    # TODO how to pass parameter to poller?
    return redirect(url_for('poller'))



@app.route('/poller')
@login_required
def poller():
    user = 'alexei'
    polls = query_db("SELECT * FROM polls WHERE poller = ?",[user])

    if len(polls) == 0:
        # create default poll with eandom code
        pollcode = int(random.random()*10000)
        pollvalues = "A B C D"
        status = 0
        db = get_db()
        db.execute("INSERT INTO polls (poller, pollcode, pollvalues, status) VALUES (?,?,?,?)",
                   [user, pollcode, pollvalues, 1])
        db.commit()
    else:
        poll = polls[0]
        pollcode = poll['pollcode']
        pollvalues = poll['pollvalues']
        status =  poll['status']

    voterows = query_db("SELECT * FROM votes WHERE pollcode = ?",[pollcode])
    votes = [v["choice"] for v in voterows]

    c = Counter(votes)

    labels = pollvalues.split()
    if status == 0:
        values = []
    else:
        values = [c[l] for l in labels]

    hostname = socket.gethostname()
    #ip_address = socket.gethostbyname(hostname)


    return render_template("poller.html", votes=votes, pollcode=pollcode, host=hostname, pollvalues = pollvalues, status=status, labels = json.dumps(labels), values = json.dumps(values))

@app.route('/changepoll', methods=['GET', 'POST'])
@login_required
def changepoll():
    user = "alexei"
    if request.method == 'POST':
        pollcode =  request.form['pollcode']
        pollvalues = request.form['pollvalues']

        # TODO check pollcode doesn't already exist
        db = get_db()
        # clear current poll(s)
        db.execute("DELETE FROM polls WHERE poller = ?", [user])

        # Add new poll
        db.execute("INSERT INTO polls (poller, pollcode, pollvalues, status) VALUES (?,?,?,?)",
                   [user, pollcode, pollvalues, 1])
        db.commit()
    return clearvotes(pollcode)

@app.route('/changestatus', methods=['GET', 'POST'])
@login_required
def changestatus():
    user = "alexei"
    if request.method == 'POST':
        pollcode =  request.form['pollcode']
        status = int(request.form['status'])

        db = get_db()
        # clear current poll(s)
        db.execute("UPDATE polls SET status = ? WHERE pollcode = ?", [status, pollcode])
        db.commit()
    return redirect(url_for('poller'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        print(request.form)
        email = request.form['email']
        password = request.form['password']
        error = None

        if email == "alexei@entropy.energy" and password == "pollnow":
            user = User("alexei")
        else:
            user = User(None)

        # user should be an instance of your `User` class
        login_user(user)

        return redirect(url_for('poller'))
    return render_template('login.html')

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

