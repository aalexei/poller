#!/usr/bin/env python3
import justpy as jp
from requests_oauthlib import OAuth2Session
from collections import Counter
import json
import random
import altair as alt

# hold all polls in running memory`
current_polls = {}

choice_types = [
    'A B C D E',
    'A B C D',
    'A B C',
    'A B',
    'Yes No',
    'True False',
    ]

def randomVotes(choices, N):
    values = choices.split()
    votes = {}
    for i in range(N):
        v = random.choice(values)
        votes[random.randrange(1,9999)] = v
    return votes



@jp.SetRoute('/')
@jp.SetRoute('/{pollid:int}')
def pollee(request):
    wp = jp.WebPage()
    col = jp.Div(a=wp, classes="flex flex-col p-5")

    pollid = request.path_params.get("pollid")
    if pollid not in current_polls:
        jp.Div(a=col, text="No poll by that ID", classes="w-full text-4xl text-center")

    else:
        poll = current_polls[pollid]

        # pretend vote already cast
        sid = request.session_id
        poll['votes'][sid] = 'B'

        div = jp.Div(a=col, classes="w-full")
        jp.Div(a=div, text=f"Poll: {pollid}", classes="text-4xl text-center")

        div = jp.Div(a=col, classes="w-full flex flex-col")
        vote = poll['votes'].get(sid)
        for k in poll['choices'].split():
            if vote==k:
                state = "bg-green-600"
            else:
                state = "bg-indigo-600 hover:bg-indigo-700 focus:ring-indigo-500"
            btn=jp.Button(a=div,
                          text=k,
                          classes=f"items-center rounded-md border border-transparent px-4 py-4 text-white shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 {state}",
                          )

        jp.Button(a=div,
                  text=f"Clear",
                  classes="items-center rounded-md border px-4 py-4 ")

    return wp

async def vote(self, msg):
    poll = current_polls[msg.page.pollid]



@jp.SetRoute('/poller')
def poller(request):

    # TODO login mechanism
    user = "aalexei"

    # grab poll if one already set
    for pid, p in current_polls.items():
        if p.get('user')==user:
            poll = p
            pollid = pid
            break
    else:
        # default poll
        # TODO pollid
        pollid = 1234
        poll = {'user':user, 'choices':'A B C D', 'votes':{},}
        current_polls[pollid] = poll
        poll['votes'] = randomVotes(poll['choices'],30)


    wp = jp.WebPage()
    wp.pollid = pollid
    col = jp.Div(a=wp, classes="flex flex-col p-5")
    #
    # Poll URL
    #
    div = jp.Div(a=col, classes="w-full")
    jp.Div(a=div, text=pollid, classes="text-4xl text-center")

    #
    # Results
    #
    div = jp.Div(a=col, classes="w-full")
    # totals
    C = Counter()
    for v in poll['votes'].values():
        C.update(v)

    choices = poll['choices']
    votes = [C[c] for c in choices]

    chart_def ={
        'chart':{'type':'bar'},
        'title':{'text':''},
        'xAxis':{'categories':choices, 'labels': {'style':{'fontSize':'24px'}}},
        'yAxis':{'title':{'text':'Votes'}, 'allowDecimals':False},
        'plotOptions': {
            'bar': {
                #'grouping': False,
                'groupPadding': 0,
                'maxPointWidth': 0,
                'pointPadding': 0,
                'showInLegend': False,
            }
        },
        'credits':{'enabled':False},
        'series':[{'data':votes}],
    }
    wp.chart = jp.HighCharts(a=div, classes='w-full', options=json.dumps(chart_def))

    #
    # Controls
    #
    div = jp.Div(a=col, classes="w-full")

    jp.Label(a=div, text="Choices:")
    sel = jp.Select(a=div, name="choices",
                    change=choiceChange,
                    classes="my-3 block w-full rounded-md border border-gray-300 bg-white py-2 px-3 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-indigo-500 sm:text-sm")
    for choices in choice_types:
        if choices == poll['choices']:
            jp.Option(a=sel, label=choices, value=choices, selected=True)
        else:
            jp.Option(a=sel, label=choices, value=choices)

    div = jp.Div(a=col, classes="w-full")
    jp.Button(a=div, text="Clear Votes")



    return wp

async def choiceChange(self,msg):
    print('Choice', msg, msg.target.value)

    poll = current_polls[msg.page.pollid]
    poll['choices'] = msg.target.value
    poll['votes'] = randomVotes(poll['choices'], 30)

    for page in jp.WebPage.instances.values():
        await page.reload()
        #jp.run_task(msg.page.update())


jp.justpy()
