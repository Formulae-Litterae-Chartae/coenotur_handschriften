from flask import current_app
from typing import Dict, List, Union, Tuple
from itertools import product
from fake_es import FakeElasticsearch
import re


PRE_TAGS = "</small><strong>"
POST_TAGS = "</strong><small>"
HIGHLIGHT_CHARS_BEFORE = 30
HIGHLIGHT_CHARS_AFTER = 30
range_agg = {'date_range': {'field': 'min_date', 'format': 'yyyy',
                            'ranges': [{'key': '<499', 'from': '0002', 'to': '0499'},
                                       {'key': '500-599', 'from': '0500', 'to': '0599'},
                                       {'key': '600-699', 'from': '0600', 'to': '0699'},
                                       {'key': '700-799', 'from': '0700', 'to': '0799'},
                                       {'key': '800-899', 'from': '0800', 'to': '0899'},
                                       {'key': '900-999', 'from': '0900', 'to': '0999'},
                                       {'key': '>1000', 'from': '1000'}]}}
no_date_agg = {'missing': {'field': 'min_date'}}
AGGREGATIONS = {'range': range_agg,
                'no_date': no_date_agg,
                'all_docs': {'global': {},
                             'aggs': {
                                 'range': range_agg,
                                 'no_date': no_date_agg
                             }}}
HITS_TO_READER = 10000


def build_sort_list(sort_str: str) -> Union[str, List[Union[Dict[str, Dict[str, str]], str]]]:
    if sort_str in ['_id', 'signature']:
        return 'signature'
    if sort_str == 'date_asc':
        return [{'mid_date': {'order': 'asc'}}, 'signature']
    if sort_str == 'date_desc':
        return [{'mid_date': {'order': 'desc'}}, 'signature']


def advanced_query_index(simple_q: str = '',
                         identifier: str = '',
                         orig_place: str = '',
                         orig_place_cert: list = None,
                         orig_year_start: str = '',
                         orig_year_end: str = '',
                         ms_item: str = '',
                         person: str = '',
                         person_role: list = None,
                         person_identifier: str = '',
                         provenance: str = '',
                         with_digitalisat: str = '',
                         with_scribe: str = '',
                         with_illuminations: str = '',
                         with_exlibris: str = '',
                         with_tironoten: str = '',
                         with_neumierung: str = '',
                         with_ink_analysis: str = '',
                         sort: str = '_id') -> Tuple[List[Dict[str, Union[str, list, dict]]],
                                                                            int,
                                                                            dict]:
    if not current_app.elasticsearch:
        return [], 0, {}
    # all parts of the query should be appended to the 'must' list. This assumes AND and not OR at the highest level
    sort = build_sort_list(sort)
    body_template = dict({"query": {"bool": {"must": []}}, "sort": sort, 'size': 10000, 'aggs': AGGREGATIONS})
    search_highlight = {'identifier': {}, 'ms_item': {}, 'provenance': {}, 'with_digitalisat': {}}
    if simple_q:
        search_highlight.update({'person.name': {}, 'orig_place.place': {}})
    if with_digitalisat in ['True', True]:
        body_template['query']['bool']['must'].append({'regexp': {'with_digitalisat': {'value': '.*'}}})
    if with_scribe in ['True', True]:
        body_template['query']['bool']['must'].append({'nested': {'path': 'person', 'query': {'match': {'person.role': 'Schreiber'}},
                                                       'inner_hits': {'highlight': {'fields': {'person.role': {}},
                                                                           'pre_tags': [PRE_TAGS],
                                                                           'post_tags': [POST_TAGS],
                                                                           'encoder': 'html'}}}})
    for bool_arg, arg_name in [(with_exlibris, 'exlibris'),
                               (with_illuminations, 'illuminated'),
                               (with_neumierung, 'musicNotation'),
                               (with_tironoten, 'tironoten'),
                               (with_ink_analysis, 'ink_analysis')]:
        if bool_arg in ['True', True]:
            body_template['query']['bool']['must'].append({'term': {arg_name: True}})
    fields = {'flat_fields':
                  {'ms_item': ms_item,
                   'provenance': provenance
                   },
              'nested_fields':
                  {'orig_place': {'orig_place.place': orig_place, 'orig_place.cert': orig_place_cert},
                   'person': {'person.name': person, 'person.role': person_role, 'person.identifier': person_identifier}},
              'date_fields':
                  {'min_date': orig_year_start,
                   'max_date': orig_year_end},
              'keyword_fields': ['orig_place.cert',
                                 'person.role',
                                 'person.identifier'],
              'simple_q_fields':
                  ['identifier.id',
                   'ms_item',
                   'provenance',
                   'person.name',
                   'orig_place.place']
              }

    body_template['highlight'] = {'fields': search_highlight,
                                  'pre_tags': [PRE_TAGS],
                                  'post_tags': [POST_TAGS],
                                  'encoder': 'html'
                                  }

    if simple_q:
        bool_clauses = []
        for s_field in fields['simple_q_fields']:
            clauses = []
            for term in simple_q.lower().split():
                if '*' in term or '?' in term:
                    clauses.append([{'span_multi': {'match': {'wildcard': {s_field: term}}}}])
                else:
                    clauses.append([{'span_term': {s_field: term}}])
            for clause in product(*clauses):
                if '.' in s_field:
                    bool_clauses.append({'nested': {'path': s_field.split('.')[0], 'query': {'bool': {'must': [{'span_near': {'clauses': list(clause), 'slop': 100, 'in_order': False}}]}}}})
                else:
                    bool_clauses.append({'span_near': {'clauses': list(clause), 'slop': 100, 'in_order': False}})
        body_template['query']['bool']['must'].append({'bool': {'should': bool_clauses, 'minimum_should_match': 1}})
    for k, v in fields['flat_fields'].items():
        bool_clauses = []
        if v:
            clauses = []
            for term in v.lower().split():
                if '*' in term or '?' in term:
                    clauses.append([{'span_multi': {'match': {'wildcard': {k: term}}}}])
                else:
                    clauses.append([{'span_term': {k: term}}])
            for clause in product(*clauses):
                bool_clauses.append({'span_near': {'clauses': list(clause), 'slop': 0, 'in_order': False}})
            body_template['query']['bool']['must'].append({'bool': {'should': bool_clauses, 'minimum_should_match': 1}})
    nested_clauses = []
    for k, v in fields['nested_fields'].items():
        bool_clauses = []
        sub_value_clauses = []
        for sub_key, sub_value in v.items():
            if sub_value:
                if sub_key in fields['keyword_fields']:
                    if isinstance(sub_value, list):
                        if any(sub_value):
                            sub_value_clauses.append({'bool': {'should': [{'match': {sub_key: x}} for x in sub_value], 'minimum_should_match': 1}})
                    else:
                        sub_value_clauses.append({'match': {sub_key: sub_value}})
                else:
                    clauses = []
                    for term in sub_value.lower().split():
                        if '*' in term or '?' in term:
                            clauses.append([{'span_multi': {'match': {'wildcard': {sub_key: term}}}}])
                        else:
                            clauses.append([{'span_term': {sub_key: term}}])
                    for clause in product(*clauses):
                        bool_clauses.append({'span_near': {'clauses': list(clause), 'slop': 0, 'in_order': False}})
        if bool_clauses or sub_value_clauses:
            nested_clauses.append({'nested': {'path': k, 'query': {'bool': {'must': bool_clauses + sub_value_clauses}},
                                              'inner_hits': {'highlight': {'fields': {x: {} for x in v.keys()},
                                                                           'pre_tags': [PRE_TAGS],
                                                                           'post_tags': [POST_TAGS],
                                                                           'encoder': 'html'}}}})
    body_template['query']['bool']['must'].append({'bool': {'should': nested_clauses, 'minimum_should_match': 1}})

    if orig_year_start or orig_year_end:
        date_clauses = []
        if orig_year_end:
            date_clauses.append({'range': {'min_date': {'lte': '{:04}'.format(int(orig_year_end))}}})
        if orig_year_start:
            date_clauses.append({'range': {'max_date': {'gte': '{:04}'.format(int(orig_year_start))}}})
        body_template['query']['bool']['must'].append({'bool': {'must': date_clauses}})

    search = current_app.elasticsearch.search(index='coenotur', doc_type="", body=body_template)

    if current_app.config["SAVE_REQUESTS"]:
        req_name = "{q}&{id}&" \
                   "{o_p}&{o_p_c}&{y_s}&{y_e}&" \
                   "{ms_i}&{person}&{pers_r}&" \
                   "{pers_id}&{prov}&{w_dig}&" \
                   "{w_scr}&{w_ill}&" \
                   "{w_ex}&{w_tiro}&{w_neu}&{w_ink}&{sort}".format(
            q=re.sub(r'[\*\?\s]', '+', simple_q), id=identifier, o_p=orig_place, o_p_c='+'.join(orig_place_cert), y_s=orig_year_start,
            y_e=orig_year_end, ms_i=ms_item, person=person, pers_r='+'.join(person_role), pers_id=person_identifier,
            prov=provenance, w_dig=with_digitalisat, w_scr=with_scribe, w_ill=with_illuminations, w_ex=with_exlibris,
            w_tiro=with_tironoten, w_neu=with_neumierung, w_ink=with_ink_analysis, sort=sort)
        req_name = req_name.replace('/', '-')
        req_name = re.sub(r'[\*\?\s]', '+', req_name)
        fake = FakeElasticsearch(req_name, "advanced_search")
        fake.save_request(body_template)
        # Remove the textual parts from the results
        fake.save_ids([{"id": hit['_id']} for hit in search['hits']['hits']])
        fake.save_response(search)
        fake.save_aggs(search['aggregations'])

    return search['hits']['hits'], search['hits']['total'], search['aggregations']
