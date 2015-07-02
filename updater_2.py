# updates voting records
import scrapeutils
import vpapi
import authentication
from lxml import html, etree
import re

vpapi.parliament('cz/senat')
vpapi.authorize(authentication.username,authentication.password)
vpapi.timezone('Europe/Prague')


o2id = {}
organizations = vpapi.getall("organizations")
for org in organizations:
    o2id[org['name']] = org['id']

p2id = {}
persons = vpapi.getall('people')
for p in persons:
    p2id[p['name']] = p['id']

def pp2id(name,date,p2id):
    if name == 'Jiří Dienstbier':
        if date < '2011-01-08':
            return '218'
        else:
            return '253'
    else:
        return p2id[name]
    
scrapeutils.USE_WEBCACHE = False
url = "http://senat.cz/xqw/xervlet/pssenat/hlasa?S=&T=&H=&N=&K=&ID=275&Str=1&Poc=20000"
domtree = html.fromstring(scrapeutils.download(url))
scrapeutils.USE_WEBCACHE = True

def result2result(r):
    if r == 'přijato':
        return 'pass'
    else:
        return 'fail'

#motions, vote-events, votes:
def guess_majority(quorum,present):
    if int(quorum) == 49:
        return 'two-thirds representatives majority'
    if int(quorum) == 41 and int(present)<81:
        return 'all representatives majority'
    else:
        return 'simple majority'

def option2option(opt):
    if opt == "A":
        return "yes"
    if opt == "N":
        return "no"
    if opt == "X":
        return "abstain"
    if opt == "T":
        return "secret"
    else: #0
        return "absent"

table = domtree.xpath('//table')[0]
trs = table.xpath('tr')
for tr in trs:
    votes = []
    tds = tr.xpath('td')
    iid = re.search('G=(\d{1,})',tds[6].xpath('a/@href')[0]).group(1).strip()
    print(iid)
    try:
        motion = {
            "text": tds[2].xpath('span//text()')[0],
            "result": result2result(tds[5].xpath('text()')[0]),
            "id": iid
        }
    except:
        motion = {
            "id": iid
        }
    
    vote_event = {
        "result": result2result(tds[5].xpath('text()')[0]),
        "id": iid,
        "motion_id": iid,
        "start_date": scrapeutils.cs2iso(tds[3].xpath('text()')[0]) + "T12:00:00"
    }
    
    url1 = "http://www.senat.cz/xqw/xervlet/pssenat/hlasy?G=" + iid
    domtree1 = html.fromstring(scrapeutils.download(url1))
    
    tables = domtree1.xpath('//table')
    try:
        quorum = int(re.search('BA=(\d{1,})',tables[0].xpath('tr/td')[1].text).group(1).strip())
        present = int(re.search('MNO=(\d{1,})',tables[0].xpath('tr/td')[0].text).group(1).strip())
    
        motion['requirement'] = guess_majority(quorum,present)
        
        h2s = domtree1.xpath('//h2')
        h2s.pop(0)
        j = 0
        tables.pop(0)
        for table in tables:
            tds = table.xpath('tr/td')
            for td in tds:
                li = td.text.strip().split('\xa0')
                vote = {
                    "vote_event_id": iid,
                    "voter_id": pp2id(" ".join([li[2],li[3]]),vote_event['start_date'],p2id),
                    "option": option2option(li[0]),
                    "group_id": o2id[h2s[j].text.strip()]
                }
                votes.append(vote)
            j += 1
        
        ex = vpapi.get("motions",where={"id":iid})
        if len(ex['_items']) < 1:
            vpapi.post("motions",motion)
            vpapi.post("vote-events",vote_event)
            vpapi.post("votes",votes)
        else:
            break
    except:
        print("XXX:" + iid)
        nothing = 0 # "Zmatečné hlasování"


