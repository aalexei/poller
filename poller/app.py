#!/usr/bin/env python3
import sqlite3, uuid, json, socket
from flask import g, Flask
from flask import session, redirect, url_for, request, render_template, flash, jsonify
from collections import Counter
import functools
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
import random
from itsdangerous import URLSafeTimedSerializer
from itsdangerous.exc import BadSignature
import config


#login_manager = LoginManager()

# Borrowed code from
# https://flask.palletsprojects.com/en/1.1.x/patterns/sqlite3/
#
INVITE_TIMEOUT = 3*24*60*60

app = Flask(__name__)
# secret key
app.secret_key = b'\x060W}\x10\x03\x00\xf7$[\xc6H\x88\xa6\x87\x0c'

#login_manager.init_app(app)
login = LoginManager(app)
login.login_view = 'login'

DATABASE = config.DATABASE

@login.user_loader
def load_user(uid):
    userdata =  query_db("SELECT * FROM users WHERE email = ?",[uid], one=True)
    if userdata is not None:
        return User(userdata)
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
def init_db():
    '''
    Initialise the database tables (not users)
    '''
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()

def init_users():
    '''
    Initialise the user database table
    '''
    with app.app_context():
        db = get_db()
        with app.open_resource('schema_users.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.execute("INSERT INTO users (email, passhash, admin) VALUES (?,?,?)",
                    ["<admin-email>",
                     generate_password_hash('<admin-pass>'),
                     1])
        db.commit()

def init_all():
    init_db()
    init_users()


# convenience function for queries
def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


class User(object):
    def __init__(self, userdata):

        self.id = userdata['email']
        self.passhash = userdata['passhash']
        self.admin = userdata['admin']
       
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

    @property
    def is_admin(self):
        return self.admin==1



@app.route('/', methods=['GET','POST'])
def default():
    if request.method == 'POST':
        pollcode =  request.form['pollcode']
        return redirect('/{}'.format(pollcode))

    return render_template("choosepoll.html")
  
@app.route('/<int:pollcode>')
def index(pollcode):
    error = None

    if 'uid' not in session:
        # Assign a new uuid
        # TODO base it on comp/ip too?
        session['uid'] = uuid.uuid4().hex

    if pollcode is not None:
        # Is the poll still valid?
        poll = query_db("SELECT * FROM polls WHERE pollcode = ?",[pollcode], one=True)
        if poll is None:
            error = "Poll '{}' doesn't exist".format(pollcode)
        else:
            # Check to see if the user already voted
            vote = None
            first = False
            uid = session['uid']
            allvotes = query_db("SELECT * FROM votes WHERE pollcode = ? ORDER BY created ASC",[pollcode])
            votes = len(allvotes)
            prev_vote =  query_db("SELECT * FROM votes WHERE pollcode = ? AND userid = ?",[pollcode, uid])
            if len(prev_vote)>0:
                vote = prev_vote[0]["choice"]
                if allvotes[0]['userid'] == uid:
                    first = True

            labels = poll["pollvalues"].split()
            return render_template("poll.html", pollcode=pollcode, values=labels, vote=vote, votes=votes, first=first)

    if error is not None:
        flash(error)
       
    return render_template("choosepoll.html")


@app.route('/vote', methods=('GET', 'POST'))
def vote():
    error = None
    uid = session['uid']
    if request.method == 'POST':
        pollcode = request.form['pollcode']
        vote = request.form['vote']

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

    return redirect(url_for('index',pollcode=pollcode))


@app.route('/_get_votes/<int:pollcode>')
def get_votes(pollcode):
    c = query_db("SELECT COUNT(userid) FROM votes WHERE pollcode = ?",[pollcode], one=True)[0]
    return jsonify({'votes': c})

@app.route('/clear')
def clearuid():
    for key in ['uid', 'pollcode']:
        if key in session:
            del session[key]

    flash("Cleared session data")
    return redirect(url_for('index'))

@app.route('/clearvotes/<pollcode>')
@login_required
def clearvotes(pollcode):
    db = get_db()
    db.execute("DELETE FROM votes WHERE pollcode = ?", [pollcode])
    db.execute("UPDATE polls SET status = 0 WHERE pollcode = ?", [pollcode])
    db.commit()

    return redirect(url_for('poller'))

@app.route('/poller')
@login_required
def poller():
    user = current_user.id
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

    host = config.HOSTNAME

    return render_template("poller.html", votes=votes, pollcode=pollcode, host=host, pollvalues = pollvalues, status=status, labels = json.dumps(labels), values = json.dumps(values))

@app.route('/changepoll', methods=['GET', 'POST'])
@login_required
def changepoll():
    user = current_user.id
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

@app.route('/changecode/<int:pollcode>')
@login_required
def changecode(pollcode):
    user = current_user.id
    error = None
    if pollcode is not None:

        codes = query_db("SELECT pollcode FROM polls")
        for t in range(30):
            newcode = int(random.random()*10000)
            if newcode not in codes:
                break
        else:
            error = "Couldn't assign unique new code"

        if error is not None:
            flash(error)
        else:
            db = get_db()
            # Clear votes on old code
            db.execute("DELETE FROM votes WHERE pollcode = ?", [pollcode])
            # Update pollcode on poll
            db.execute("UPDATE polls SET status = 0, pollcode = ? WHERE pollcode = ?", [newcode, pollcode])
            db.commit()
    return redirect(url_for('poller'))


@app.route('/togglestatus/<pollcode>')
@login_required
def togglestatus(pollcode):
    user = current_user.id
    poll = query_db("SELECT * FROM polls WHERE pollcode = ?",[pollcode], one=True)
    if poll is not None:
        status = int( not bool(poll['status']))
        db = get_db()
        db.execute("UPDATE polls SET status = ? WHERE pollcode = ?", [status, pollcode])
        db.commit()
    return redirect(url_for('poller'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        error = None

        dbuser =  query_db("SELECT * FROM users WHERE email = ?",[email], one=True)

        if dbuser is None or not check_password_hash( dbuser['passhash'], password):
            error = "Invalid login"
        else:
            user = User(dbuser)
            login_user(user)
            return redirect(url_for('poller'))

        if error is not None:
            flash(error)
    return render_template('login.html')

@app.route("/logout")
@login_required
def logout():
    user = current_user.id

    db = get_db()
    polls = query_db("SELECT * FROM polls WHERE poller = ?",[user])
    for poll in polls:
        db.execute("DELETE FROM votes WHERE pollcode = ?", [poll["pollcode"]])
    db.execute("DELETE FROM polls WHERE poller = ?", [user])
    db.commit()
               
    logout_user()
    return redirect(url_for("login"))


@app.route("/makeinvitation", methods=['GET', 'POST'])
@login_required
def make_invitation():
    if not current_user.is_admin:
        flash("Not authorised")
        return redirect(url_for("login"))

    url = None
    inviteemail = None
    if request.method == 'POST':
        inviteemail = request.form['inviteemail']

        if inviteemail is not None:
            ts = URLSafeTimedSerializer(app.config["SECRET_KEY"])
            token = ts.dumps(inviteemail, salt='the blah email')

            url = 'http://{}/register/{}'.format(config.HOSTNAME,token)

    return render_template('makeinvitation.html', url=url, email=inviteemail)

@app.route("/register/<token>", methods=['GET', 'POST'])
def register(token):
    ts = URLSafeTimedSerializer(app.config["SECRET_KEY"])
    try:
        email = ts.loads(token, salt="the blah email", max_age=INVITE_TIMEOUT)
    except BadSignature:
        error = "Token incorrect or expired"
        suggestion = "Request a new token to use Poller"
        return render_template('error.html', error=error, suggestion=suggestion)
    error = None

    if request.method == 'POST':
        password1 = request.form['password1']
        password2 = request.form['password2']

        if password1 != password2:
            error = "Passwords don't match"
        else:
            # create user
            db = get_db()
            db.execute("DELETE FROM users WHERE email = ?", [email])
            db.execute("INSERT INTO users (email, passhash, admin) VALUES (?,?,0)", [
                email, generate_password_hash(password1)])
            db.commit()
            return redirect(url_for("login"))

    if error is not None:
        flash(error)

    return render_template('register.html', token=token)
