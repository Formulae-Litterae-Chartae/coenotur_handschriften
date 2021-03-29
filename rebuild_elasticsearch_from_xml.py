from elasticsearch import Elasticsearch
from glob import glob
import re
import json
import datetime
from lxml import etree
from collections import defaultdict
import sys

es_url = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:9200'

# For local ES
# es = Elasticsearch('http://localhost:9200')
# For Bonsai ES
es = Elasticsearch(es_url)

# This gets rid any index that is not current
print('Removing old indices')
old_index_number = 0
old_indices = []
for k, v in es.indices.get_alias().items():
    if 'all' not in v['aliases']:
        es.indices.delete(k)
        print('Index {} has been removed'.format(k))
    else:
        old_indices.append(k)
        old_index_number = int(re.sub(r'coenotur_v(\d+)', r'\1', k))
        
new_index = 'coenotur_v{}'.format(old_index_number + 1)

files = glob('xmls/*.xml')
namespaces = {'tei': 'http://www.tei-c.org/ns/1.0'}

# The 'auto_analyzer' and 'auto_filter' are for the 'autocomplete field. Since this is not supported, and may never be necessary, I am commenting them out.
auto_filter = {"filter": {"autocomplete_filter": {"type": "edge_ngram", "min_gram": 2, "max_gram": 20}}}
auto_analyzer = {"analyzer": {"autocompletion": {"type": "custom", "tokenizer": "standard", "filter": ["lowercase", "autocomplete_filter"]}}}
# new_indices should also have the latest index name in it.
new_indices = {}
index_properties = {'identifier': {'type': 'text'}, 'date_string': {'type': 'keyword'}, 'signature': {'type': 'keyword'}}
index_properties.update({'min_date': {'type': 'date', 'format': 'yyyy'},
                         'max_date': {'type': 'date', 'format': 'yyyy'}})
index_properties.update({'orig_place': {"type": "nested", "properties": {"cert": {"type": "keyword"}, "place": {"type": "text"}, "source": {"type": "text"}}}})
index_properties.update({'ms_item': {"type": "text"}})
index_properties.update({'person': {"type": "nested", "properties": {"name": {"type": "text"}, "role": {"type": "keyword"}, "identifier": {"type": "keyword"}}}})
index_properties.update({'provenance': {"type": "text"}})
index_properties.update({'autocomplete_orig_place': {"type": "nested", "properties": {"cert": {"type": "keyword"}, "place": {"type": "text", "analyzer": "autocompletion", "search_analyzer": "standard"}}}})
index_properties.update({'autocomplete_ms_item': {"type": "text", "analyzer": "autocompletion", "search_analyzer": "standard"}})
index_properties.update({'autocomplete_person': {"type": "nested", "properties": {"name": {"type": "text", "analyzer": "autocompletion", "search_analyzer": "standard"}, "role": {"type": "keyword"}, "identifier": {"type": "keyword"}}}})
index_properties.update({'with_digitalisat': {'type': 'keyword'}})
index_properties.update({'illuminated': {'type': 'boolean'}})
index_properties.update({'musicNotation': {'type': 'boolean'}})
index_properties.update({'exlibris': {'type': 'boolean'}})
index_properties.update({'tironoten': {'type': 'boolean'}})
index_properties.update({'named_scribe': {'type': 'boolean'}})


for file in files:
    xml = etree.parse(file)
    # Get identifiers and alt ids
    ids = list()
    altids = list()
    msNames = list()
    for c in xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:msIdentifier/*', namespaces=namespaces):
        if c.tag == '{http://www.tei-c.org/ns/1.0}altIdentifier':
            altids.append(c.get('source') + ' ' + ' '.join(c.xpath('.//text()')).strip())
        elif c.tag == '{http://www.tei-c.org/ns/1.0}msName':
            msNames.append(''.join(c.xpath('.//text()')).strip())
        else:
            if c.text:
                ids.append(''.join(c.xpath('.//text()')).strip())
    identifiers = ', '.join(msNames) + '; ' + ', '.join(ids) + '; ' + '; '.join(altids)
    signature = ' '.join(xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:titleStmt/tei:title//text()', namespaces=namespaces))
    
    # Get dates
    dates = {'min_dates': [], 'max_dates': []}
    date_strings = []
    for d in xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:history/tei:origin/tei:p/tei:origDate', namespaces=namespaces):
        if d.get('notBefore'):
            dates['min_dates'].append(d.get('notBefore'))
        if d.get('notAfter'):
            dates['max_dates'].append(d.get('notAfter'))
        if d.get('when'):
            dates['min_dates'].append(d.get('when'))
            dates['max_dates'].append(d.get('when'))
        date_strings.append(re.sub(r'\s+', ' ', ''.join(d.xpath('.//text()'))))
    date_string = ' '
    if date_strings:
        date_string = '; '.join(date_strings)
        
    # Get origPlace
    places = []
    for p in xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:history/tei:origin/tei:p/tei:origPlace', namespaces=namespaces):
        places.append({'cert': p.get('cert'), 'place': re.sub(r'\s+', ' ', ''.join(p.xpath('.//text()'))), 'source': p.get('source', '')})
        
    # Get msItems
    items = set()
    for i in xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:msContents/tei:msItem', namespaces=namespaces):
        author = re.sub(r'\s+', ' ', ''.join(i.xpath('tei:author//text()', namespaces=namespaces)))
        title = re.sub(r'\s+', ' ', ''.join(i.xpath('tei:title//text()', namespaces=namespaces)))
        item = ''
        if author and title:
            item = author + ', ' + title
        else:
            item = author + title
        sub_items = set()
        for sub_i in i.xpath('tei:msItem', namespaces=namespaces):
            sub_author = re.sub(r'\s+', ' ', ''.join(sub_i.xpath('tei:author//text()', namespaces=namespaces)))
            sub_title = re.sub(r'\s+', ' ', ''.join(sub_i.xpath('tei:title//text()', namespaces=namespaces)))
            sub_item = ''
            if author and title:
                sub_item = author + ', ' + title
            elif author or title:
                sub_item = author + title
            if sub_item != item:
                sub_items.add(sub_item)
        if sub_items and sub_items != item:
            item += ' - ' + ', '.join(sub_items)
        if item:
            items.add(item)
    items = list(items)
            
    # Get persons
    persons = []
    named_scribe = False
    for n in xml.xpath('//tei:persName', namespaces=namespaces):
        persons.append({'name': re.sub(r'\s+', ' ', ''.join(n.xpath('.//text()', namespaces=namespaces))), 'role': n.get('type'), 'identifier': n.get('n')})
        if n.get('type') == 'scribe': 
            named_scribe = True
        
    # Get provenance
    provenance_strings = []
    for prov in xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:history/tei:provenance', namespaces=namespaces):
        provenance_strings.append(re.sub(r'\s+', ' ', ''.join(prov.xpath('.//text()', namespaces=namespaces))))
        
    with_digitalisat = []
    for idno in xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:additional/tei:surrogates/tei:bibl/tei:idno/text()', namespaces={'tei': 'http://www.tei-c.org/ns/1.0'}):
        with_digitalisat.append(idno)
        
    illuminated = False
    if xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:physDesc/tei:decoDesc/tei:decoNote/tei:p/text()', namespaces=namespaces):
        illuminated = True
        
    musicNotation = False
    if xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:physDesc/tei:musicNotation/tei:p/text()', namespaces=namespaces):
        musicNotation = True
        
    exlibris = False
    if xml.xpath('//tei:p[@n="Exlibris"]', namespaces=namespaces):
        exlibris = True
        
    tironoten = False
    if xml.xpath('//tei:p[@n="tironischen Note"]', namespaces=namespaces):
        tironoten = True
    
    if not es.indices.exists(new_index):
        print("Creating index {}".format(new_index))
        # 1 shard searches faster
        es.indices.create(index=new_index, body={"settings": {"index": {"number_of_shards": 1},
                                                              "analysis": {"filter": auto_filter["filter"],
                                                                           "analyzer": auto_analyzer["analyzer"]}},
                                                              "mappings": {"properties": index_properties}})
    body = {'identifier': identifiers, 
            'signature': signature,
            'date_string': date_string,
            'ms_item': items,
            'person': persons, 
            'provenance': '; '.join(provenance_strings),
            'autocomplete_person': persons,
            'autocomplete_orig_place': places, 
            'autocomplete_ms_item': items,
            'illuminated': illuminated,
            'musicNotation': musicNotation,
            'exlibris': exlibris,
            'tironoten': tironoten,
            'named_scribe': named_scribe
            }
    
    if places:
        body['orig_place'] = places
    if dates['min_dates']: 
        body['min_date'] = min(dates['min_dates'])
    if dates['max_dates']:
        body['max_date'] = max(dates['max_dates']) 
    if with_digitalisat:
        body['with_digitalisat'] = with_digitalisat
    
    try:
        es.index(index=new_index, id=file.split('/')[-1].replace('.xml', ''), body=body)
    except Exception as E:
        print(E, file)
    
# delete previous aliases to each of the collections and point them instead to the new index
for index in old_indices:
    try:
        es.indices.delete_alias(index=index, name='_all')
    except Exception as E:
        print(E, 'No alias found for {}'.format(index))

es.indices.put_alias(index=new_index, name='all')
es.indices.put_alias(index=new_index, name='coenotur')
