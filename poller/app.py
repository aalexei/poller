#!/usr/bin/env python3
import sqlite3, uuid
from flask import g, Flask
from flask import session, redirect, url_for, request, render_template, flash

# Borrowed code from
# https://flask.palletsprojects.com/en/1.1.x/patterns/sqlite3/
#

app = Flask(__name__)
# secret key
app.secret_key = b'\x060W}\x10\x03\xcc\xf7$[\xc6H\x88\xa6\x87\x0c'

DATABASE = 'poller.db'

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


@app.route('/', methods=('GET', 'POST'))
def index():
    pollcode = None
    error = None

    if 'uid' not in session:
        session['uid'] = uuid.uuid4().hex

    if request.method == 'GET':
        pollcode = request.args.get('pollcode', default=None)
    elif request.method == 'POST':
        pollcode = request.form['pollcode']
    elif "pollcode" in session:
        pollcode = session["pollcode"]

    if pollcode is not None:
        poll = query_db("SELECT * FROM polls WHERE pollcode = ?",[pollcode], one=True)

        if poll is None:
            error = "Poll '{}' doesn't exist".format(pollcode)
            if 'pollcode' in session:
                del session['pollcode']
        else:
            session['pollcode'] = pollcode
            uid = session['uid']
            prev_vote =  query_db("SELECT * FROM votes WHERE pollcode = ? AND userid = ?",[pollcode, uid])
            if len(prev_vote)>0:
                return "Already Voted"
            
            return render_template("poll.html", pollcode=pollcode, values=["A", "B", "C", "D"])

    if error is not None:
        flash(error)
       
    return render_template("choosepoll.html", session=session)

@app.route('/vote', methods=('GET', 'POST'))
def vote():
    error = None
    uid = session['uid']
    if request.method == 'GET':
        pollcode = request.args.get('pollcode', default=None)
        vote = request.args.get('vote', default=None)

        if pollcode is None or vote is None:
            error = "Missing poll or vote"
        else:
            poll = query_db("SELECT * FROM polls WHERE pollcode = ?",[pollcode], one=True)
            if poll is None:
                error = "Poll '{}' doesn't exist".format(pollcode)
            elif poll['status'] == 0:
                error = "Poll '{}' is not open".format(pollcode)
            else:
                prev_vote =  query_db("SELECT * FROM votes WHERE pollcode = ? AND userid = ?",[pollcode, uid])
                if len(prev_vote)>0:
                    return "Already Voted"
                else:
                    db = get_db()
                    db.execute("INSERT INTO votes (userid, pollcode, choice) VALUES (?,?,?)",
                                           [uid, pollcode, vote])
                    db.commit()


        if error is not None:
            flash(error)
            return redirect(url_for('index'))

        return str([pollcode, uid, vote])
    return "Poll"


@app.route('/poll')
def poll():
    cur = get_db().cursor()
    return "Poll"


@app.route('/clearuid')
def clearuid():
    if 'uid' in session:
        del session['uid']

    flash("Cleared UID")
    return redirect(url_for('index'))

@app.route('/clearvotes/<pollcode>')
def clearvotes(pollcode):
    db = get_db()
    db.execute("DELETE FROM votes WHERE pollcode = ?", [pollcode])
    db.commit()

    return "Done"
