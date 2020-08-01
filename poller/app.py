#!/usr/bin/env python3
import sqlite3, uuid, json, socket
from flask import g, Flask
from flask import session, redirect, url_for, request, render_template, flash
from collections import Counter
import functools

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

            labels = poll["polltype"].split()
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
            elif poll['status'] == 0:
                error = "Poll '{}' is not open".format(pollcode)
            elif vote not in poll["polltype"].split():
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
    db.commit()

    # TODO how to pass parameter to poller?
    return redirect(url_for('poller'), pollcode=pollcode)



@app.route('/poller')
def poller():
    user = 'alexei'
    poll = query_db("SELECT * FROM polls WHERE poller = ?",[user], one=True)
    pollcode = poll['pollcode']

    voterows = query_db("SELECT * FROM votes WHERE pollcode = ?",[pollcode])
    votes = [v["choice"] for v in voterows]

    c = Counter(votes)

    labels = poll["polltype"].split()
    values = [c[l] for l in labels]

    hostname = socket.gethostname()
    #ip_address = socket.gethostbyname(hostname)

    data = {
        'labels':labels,
        'datasets': [{
            'label':'Votes',
            'data':values,
            'backgroundColor': 'rgba(81, 151, 214, 1.0)',
        }]
    }


    return render_template("poller.html", votes=votes, data = json.dumps(data), pollcode=pollcode, host=hostname)


