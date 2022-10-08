#!/usr/bin/env python3
import justpy as jp
from requests_oauthlib import OAuth2Session
from collections import Counter
import json
import random

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
        sid = request.session_id
        wp.pollid = pollid

        #
        # Title
        #
        div = jp.Div(a=col, classes="w-full")
        jp.Div(a=div, text=f"Poll: {pollid}", classes="text-4xl text-center")

        #
        # Buttons
        #
        div = jp.Div(a=col, classes="w-full flex flex-col pt-5 gap-2")
        vote = poll['votes'].get(sid)
        for k in poll['choices'].split():
            if vote==k:
                state = "bg-indigo-500"
            else:
                state = "bg-blue-300 hover:bg-blue-500 focus:ring-blue-400"
            btn=jp.Button(a=div,
                          value=k,
                          classes=f"items-center {state} rounded-md border p-4 focus:ring-2 focus:ring-offset-2",
                          click=castVote,
                          )
            jp.Span(a=btn, text=k, classes="text-white text-3xl")
            if vote==k:
                btn.disabled = True

    return wp

async def castVote(self, msg):

    pollid = msg.page.pollid
    poll = current_polls[pollid]
    poll['votes'][msg.session_id] = msg.value
    print(pollid, msg)
    await msg.page.reload()


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
    jp.Div(a=div, text=f"Poll: {pollid}", classes="text-4xl text-center")

    #
    # Results
    #
    div = jp.Div(a=col, classes="w-full")
    # totals
    C = Counter()
    for v in poll['votes'].values():
        C.update([v])

    choices = poll['choices']
    votes = [C[c] for c in choices.split()]

    chart_def ={
        'chart':{'type':'bar'},
        'title':{'text':''},
        'xAxis':{'categories':choices.split(), 'labels': {'style':{'fontSize':'24px'}}},
        'yAxis':{'title':{'text':'Votes'}, 'allowDecimals':False},
        'plotOptions': {
            'bar': {
                'grouping': False,
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
    div = jp.Div(a=col, classes="w-full flex flex-row mt-5 p-5 border border-gray-300")

    jp.Div(a=div, text="Reset poll:", classes="basis-1/4 mr-5")
    sel = jp.Select(a=div, name="choices",
                    change=choiceChange,
                    classes="basis-3/4 grow")
    for choices in choice_types:
        jp.Option(a=sel, label=choices, value=choices)

    return wp

async def choiceChange(self,msg):
    print('Choice', msg, msg.target.value)

    poll = current_polls[msg.page.pollid]
    poll['choices'] = msg.target.value
    poll['votes'] = {} #randomVotes(poll['choices'], 30)

    for page in jp.WebPage.instances.values():
        await page.reload()
        #jp.run_task(msg.page.update())


jp.justpy()
