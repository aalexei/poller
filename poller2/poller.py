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

def defaults(D,**args):
    '''
    Return dict D with **args as defaults (i.e. overriden by common keys in D)
    '''
    args.update(D)
    return args


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
        wp.role = 'pollee'

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

    for page in jp.WebPage.instances.values():
        if page.pollid == pollid and page.role == "poller":
            # There might be multiple poller pages
            page.chart.updateChart(poll)
            #await page.chart.update()
            #await page.chart.chart.update()
            #jp.run_task(page.update())
            #await page.reload()
            await page.update()

class ChartDiv(jp.Div):
    '''
    Display chart of results
    '''

    def __init__(self, **kwargs):
        super().__init__(**defaults(
            kwargs,
            delete_flag=False,
            #classes="q-pa-xs",
        ))

    #     self.setup()

    # def setup(self):

        chart_def ={
            'chart':{'type':'bar'},
            'title':{'text':''},
            'xAxis':{'categories':['A','B'], 'labels': {'style':{'fontSize':'24px'}}},
            'yAxis':{'title':{'text':'Votes'}, 'allowDecimals':False},
            'plotOptions': {
                'series': {'animation': True},
                'bar': {
                    'grouping': False,
                    'groupPadding': 0,
                    'maxPointWidth': 0,
                    'pointPadding': 0,
                    'showInLegend': False,
                }
            },
            'credits':{'enabled':False},
            'series':[{'data':[0,0]}],
        }

        self.chart = jp.HighCharts(a=self, classes='w-full', options=chart_def, delete_flag=False)

    # def setChart(self, poll):

    #     choices = poll['choices'].split()
    #     votes = poll['votes'].values()
    #     # totals
    #     C = Counter()
    #     for v in votes:
    #         print(C,v)
    #         C.update([v])
    #     counts = [C[c] for c in choices]

    #     chart_def ={
    #         'chart':{'type':'bar'},
    #         'title':{'text':''},
    #         'xAxis':{'categories':choices, 'labels': {'style':{'fontSize':'24px'}}},
    #         'yAxis':{'title':{'text':'Votes'}, 'allowDecimals':False},
    #         'plotOptions': {
    #             'series': {'animation': False},
    #             'bar': {
    #                 'grouping': False,
    #                 'groupPadding': 0,
    #                 'maxPointWidth': 0,
    #                 'pointPadding': 0,
    #                 'showInLegend': False,
    #             }
    #         },
    #         'credits':{'enabled':False},
    #         'series':[{'data':counts}],
    #     }

    #     self.delete_components()
    #     self.chart = jp.HighCharts(a=self, classes='w-full', options=chart_def, delete_flag=False)
    #     #self.chart = chart
    #     #print(chart)

    def updateChart(self, poll):

        choices = poll['choices'].split()
        votes = poll['votes'].values()
        # totals
        C = Counter()
        for v in votes:
            print(C,v)
            C.update([v])
        counts = [C[c] for c in choices]

        self.chart.options.xAxis.categories = choices
        self.chart.options.series[0].data = counts


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
        #poll['votes'] = randomVotes(poll['choices'],30)
        poll['votes'] = {}


    wp = jp.WebPage()
    wp.pollid = pollid
    wp.role = 'poller'
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
    wp.chart = ChartDiv(a=div)
    wp.chart.updateChart(poll)

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

    pollid = msg.page.pollid
    poll = current_polls[pollid]
    poll['choices'] = msg.target.value
    poll['votes'] = {} #randomVotes(poll['choices'], 30)

    for page in jp.WebPage.instances.values():
        if page.pollid == pollid and page.role == "poller":
            # There might be multiple poller pages
            page.chart.updateChart(poll)
            # page.chart.options.xAxis.categories = poll['choices'].split()
            # page.chart.options.series[0].data = poll['votes']
            #print('Updated chart')
            #await page.reload()
            await page.update()
            #await page.chart.update()
        else:
            await page.reload()
        #jp.run_task(msg.page.update())


jp.justpy()
