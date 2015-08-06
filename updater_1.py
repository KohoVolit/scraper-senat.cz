#updates people and parties (organizations)
import scrapeutils
import vpapi
import authentication
from lxml import html, etree
import re
import os.path
import logging
from datetime import date, datetime, timedelta
import argparse


LOGS_DIR = '/var/log/scrapers/cz/senat'

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

def my_put(resource, item, vpapi):
    ex = vpapi.get(resource,where={"id":item['id']})
    if len(ex['_items']) >= 1:
        #somehow vpapi.put does not work for me, so delete and post
        #vpapi.put(resource,item['id'],item)
        vpapi.delete(resource,item['id'])
    vpapi.post(resource,item)

# set-up logging to a local file
if not os.path.exists(LOGS_DIR):
	os.makedirs(LOGS_DIR)
logname = datetime.utcnow().strftime('%Y-%m-%d-%H%M%S') + '.log'
logname = os.path.join(LOGS_DIR, logname)
logname = os.path.abspath(logname)
logging.basicConfig(level=logging.DEBUG, format='%(message)s', handlers=[logging.FileHandler(logname, 'w', 'utf-8')])
logging.getLogger('requests').setLevel(logging.ERROR)

logging.info('Started')
db_log = vpapi.post('logs', {'status': 'running', 'file': logname, 'params': []})


try:
    # get all senators by districts and all political groups
    baseurl = 'http://senat.cz/'
    people = []
    groups = {}
    iid = 100001

        ## people
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

    # save senators
    j = 0
    for person in people:
        print(j)
        j += 1
        my_put("people",person,vpapi)   

        ## parties (organizations)

    # some are not available by the algorithm above:
    group = {
        "name": "Senát Parlamentu ČR",
        "classification": "chamber",
        "id": "1"
    }
    my_put("organizations",group, vpapi)

    group = {
        "name": "Nezařazení",
        "classification": "political group",
        "parent_id": "1",
        "id": str(iid)
    }
    iid += 1
    my_put("organizations",group, vpapi)
    group = {
        "name": "Senátorský klub Zelení - nezávislí",
        "classification": "political group",
        "parent_id": "1",
        "id": str(iid)
    }
    iid += 1
    my_put("organizations",group, vpapi)
    group = {
        "name": 'Senátorský klub "Nezařazení"',
        "classification": "political group",
        "parent_id": "1",
        "id": str(iid)
    }
    iid += 1
    my_put("organizations",group, vpapi)

    for group in groups:
        ids = []
        for identifier in groups[group]['identifiers']:
            ids.append(groups[group]['identifiers'][identifier])
        groups[group]['identifiers'] = ids
        my_put("organizations",groups[group],vpapi)

    vpapi.patch('logs', db_log['id'], {'status': "finished"})
except:
    vpapi.patch('logs', db_log['id'], {'status': "failed"})

