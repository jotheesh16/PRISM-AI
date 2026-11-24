import store
store.init()
with store.connect() as db:
    for row in db.execute('SELECT id,space,name,state FROM docs ORDER BY rowid'):
        print(tuple(row))
from unittest.mock import patch
from research import ask
import research
old_retrieve=research.retrieve
def rr(q,d):
 print('RETRIEVE DOCS',d)
 return old_retrieve(q,d)
research.retrieve=rr
with patch('research.chat', return_value={'status':'refuse','answer':'no','citations':[]}):
    with store.connect() as db:
        print('READY', [tuple(x) for x in db.execute("select id,state,space from docs where space='main'")])
        g=dict(db.execute("SELECT id,generation FROM docs WHERE space=? AND state='ready' ORDER BY rowid", ('main',)))
        print('GEN',g, list(g))
    r=ask('main','test',['715aed55575244a99623fcd30de254d','6a179f20733e4565a2ea76df87c3419c'])
    print('SCOPE',r['scope'])
