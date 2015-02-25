import scrapeutils
import vpapi
import authentication
from lxml import html, etree
import re

vpapi.parliament('cz/senat')
vpapi.authorize(authentication.username,authentication.password)
vpapi.timezone('Europe/Prague')

def full_name2name(fn):
    li = fn.split(' ')
    nameli = []
    for word in li:
        if (word != '') and (word[-1] != '.') and (word not in ['MBA','FCMA','MPA','MUDr']):
            nameli.append(word.replace('\xa0',''))
    name = {
        'given_name': nameli[0].strip(),
        'family_name': nameli[-1].strip(),
        'name': ' '.join(nameli).strip()
    }
    return name

# get all senators by districts and all political groups

baseurl = 'http://senat.cz/'
people = []
groups = {}
iid = 100001
for i in range(1,82):
    print(i)
    url = "http://senat.cz/senat/volby/hledani/o_obvodu.php?ke_dni=23.02.2015&O=10&kod=" + str(i)
    domtree = html.fromstring(bytes(scrapeutils.download(url),'iso-8859-1').decode('utf-8'))    #note: senat.cz incorrectly send headers as iso/latin1 and so requests save it incorrectly - so fixing it here
    tables = domtree.xpath('//table[@class="tHistory"]')
    for table in tables:
        image = baseurl[:-1] + table.xpath('tr/td/img/@src')[0].replace('_110','')
        name = full_name2name(table.xpath('tr/td/img/@alt')[0])
        ident = re.search('par_3=(\d{1,})',table.xpath('tr/td/a/@href')[0]).group(1).strip()
        people.append({
            'given_name': name['given_name'],
            'family_name': name['family_name'],
            'name': name['name'],
            'sort_name': name['family_name'] + ', ' + name['given_name'],
            'image': image,
            'id': ident,
            'identifiers': [{
                'scheme': 'senat.cz',
                'identifier': ident
            }]
        })
        links = table.xpath('tr/td/a/@href')
        
        for link in links:
            url1 = baseurl + link
            domtree1 = html.fromstring(bytes(scrapeutils.download(url1),'iso-8859-1').decode('utf-8'))
            aas = domtree1.xpath('//section[@class="membershipModule"]/dl/dd/a')
            for a in aas:
                if "klub" in a.text.lower():
                    try:
                        groups[a.text]
                    except:
                        groups[a.text] = {
                            "name": a.text.strip(),
                            "classification": "political group",
                            "parent_id": "1",
                            "identifiers": {},
                            "id": str(iid)
                        }
                        iid += 1
                    gid = re.search('par_2=(\d{1,})',a.xpath('@href')[0]).group(1).strip()
                    o = re.search('O=(\d{1,})',a.xpath('@href')[0]).group(1).strip()
                    groups[a.text]["identifiers"][gid] = {
                        "scheme": "senat.cz/" + o,
                        "identifier": gid
                    }

# save it
j = 0
for person in people:
    print(j)
    j += 1
    ex = vpapi.get("people",where={"id":person['id']})
    if len(ex['_items']) < 1:
        vpapi.post("people",person)
#vpapi.post("people",people)
group = {
    "name": "Senát Parlamentu ČR",
    "classification": "chamber",
    "id": "1"
}
# some are not available by the algorithm above:
vpapi.post("organizations",group)
group = {
    "name": "Nezařazení",
    "classification": "political group",
    "parent_id": "1",
    "id": str(iid)
}
iid += 1
vpapi.post("organizations",group)
group = {
    "name": "Senátorský klub Zelení - nezávislí",
    "classification": "political group",
    "parent_id": "1",
    "id": str(iid)
}
iid += 1
vpapi.post("organizations",group)
group = {
    "name": 'Senátorský klub "Nezařazení"',
    "classification": "political group",
    "parent_id": "1",
    "id": str(iid)
}
iid += 1
vpapi.post("organizations",group)

for group in groups:
    ids = []
    for identifier in groups[group]['identifiers']:
        ids.append(groups[group]['identifiers'][identifier])
    groups[group]['identifiers'] = ids
    vpapi.post("organizations",groups[group])

o2id = {}
organizations = vpapi.getall("organizations")
for org in organizations:
    o2id[org['name']] = org['id']

p2id = {}
persons = vpapi.getall('people')
for p in persons:
    p2id[p['name']] = p['id']


# vote-events, motions, votes
    #get people, groups

raise Exception()

url = "http://senat.cz/xqw/xervlet/pssenat/hlasa?S=&T=&H=&N=&K=&ID=275&Str=1&Poc=20000"
domtree = html.fromstring(scrapeutils.download(url))

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
    tds = tr.xpath('td')
    iid = re.search('G=(\d{1,})',tds[6].xpath('a/@href')[0]).group(1).strip()
    motion = {
        "text": tds[2].xpath('span//text()')[0],
        "result": result2result(tds[5].xpath('text()')[0]),
        "id": iid
    }
    
    vote_event = {
        "result": result2result(tds[5].xpath('text()')[0]),
        "id": iid,
        "motion_id": iid,
        "start_date": scrapeutils.cs2iso(tds[3].xpath('text()')[0])
    }
    
    url1 = "http://www.senat.cz/xqw/xervlet/pssenat/hlasy?G=" + iid
    domtree1 = html.fromstring(scrapeutils.download(url1))
    
    tables = domtree1.xpath('//table')
    quorum = int(re.search('BA=(\d{1,})',tables[0].xpath('tr/td')[1].text).group(1).strip())
    present = int(re.search('MNO=(\d{1,})',tables[0].xpath('tr/td')[0].text).group(1).strip())
    
    motion['requirement'] = guess_majority(quorum,present)
    
    h2s = domtree1.xpath('//h2').pop(0)
    j = 1
    for table in tables.pop(0):
        tds = table.xpath('tr/td')
        for td in tds:
            li = td.text.strip().split('\xa0')
            vote = {
                "vote_event_id": iid,
                "voter_id": name2id(" ".join([li[2],li[3]])),
                "option": option2option(li[0]),
                "group_id": group2id(h2s[j].strip())
            }
        j += 1    
    
    
    


#"requirement": "simple majority",
#"result": "pass",
#"id": "1839",
#"text": "Volba ověřovatelů",


#result": "pass",
#"id": "1839",
#"motion_id": "1839",
#"start_date": "1995-10-18T13:09:00",          


#"vote_event_id": "3000",
#"voter_id": "1",
#"option": "no",
#"group_id": "15",
