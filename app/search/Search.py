from flask import current_app, Markup, flash, session, g
from flask_babel import _
from string import punctuation
import re
from copy import copy
from typing import Dict, List, Union, Tuple, Set
from itertools import product
from math import floor
from random import randint


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


def suggest_word_search(**kwargs) -> Union[List[str], None]:
    """ To enable search-as-you-type for the text search

    :return: sorted set of results
    """
    results = set()
    kwargs['fragment_size'] = 1000
    field_mapping = {'autocomplete': 'text', 'autocomplete_lemmas': 'lemmas'}
    if kwargs['qSource'] == 'text':
        highlight_field = field_mapping[kwargs.get('lemma_search', 'autocomplete')]
        term = kwargs.get('q', '')
        if '*' in term or '?' in term:
            return None
        posts, total, aggs, prev_search = advanced_query_index(per_page=1000, **kwargs)
    elif kwargs['qSource'] == 'regest':
        highlight_field = 'regest'
        term = kwargs.get('regest_q', '')
        if '*' in term or '?' in term:
            return None
        posts, total, aggs, prev_search = advanced_query_index(per_page=1000, **kwargs)
    else:
        return None
    for post in posts:
        r = re.sub(r'[{}]'.format(punctuation), '', post['info'][highlight_field]).lower()
        ind = 0
        sep = ''
        while term in r[ind:]:
            if ind > 0:
                sep = ' '
            i = r.find(sep + term, ind)
            if i == -1:
                ind = i
                continue
            end_index = min(r.find(' ', i + len(term) + 30), len(r))
            if end_index == -1:
                end_index = len(r)
            results.add(r[i:end_index].strip())
            ind = i + len(sep + term)
    return sorted(results, key=str.lower)[:10]


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
                         autocomplete_ms_item: str = '',
                         autocomplete_person: str = '',
                         autocomplete_orig_place: str = '',
                         autocomplete_orig_place_cert: list = None,
                         autocomplete_person_role: list = None,
                         autocomplete_person_identifier: str = '',
                         with_digitalisat: str = '',
                         with_scribe: str = '',
                         with_illuminations: str = '',
                         with_exlibris: str = '',
                         with_tironoten: str = '',
                         with_neumierung: str = '') -> Tuple[List[Dict[str, Union[str, list, dict]]],
                                                                            int,
                                                                            dict]:
    if not current_app.elasticsearch:
        return [], 0, {}
    # all parts of the query should be appended to the 'must' list. This assumes AND and not OR at the highest level
    body_template = dict({"query": {"bool": {"must": []}}, "sort": '_id', 'size': 10000, 'aggs': AGGREGATIONS})
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
                               (with_tironoten, 'tironoten')]:
        if bool_arg in ['True', True]:
            body_template['query']['bool']['must'].append({'term': {arg_name: True}})
    fields = {'flat_fields':
                  {'identifier': identifier,
                   'ms_item': ms_item,
                   'autocomplete_ms_item': autocomplete_ms_item,
                   'provenance': provenance
                   },
              'nested_fields':
                  {'orig_place': {'orig_place.place': orig_place, 'orig_place.cert': orig_place_cert},
                   'person': {'person.name': person, 'person.role': person_role, 'person.identifier': person_identifier},
                   'autocomplete_person': {'autocomplete_person.name': autocomplete_person,
                                           'autocomplete_person.role': autocomplete_person_role,
                                           'autocomplete_person.identifier': autocomplete_person_identifier},
                   'autocomplete_orig_place': {'autocomplete_orig_place.place': autocomplete_orig_place,
                                               'autocomplete_orig_place.cert': autocomplete_orig_place_cert}},
              'date_fields':
                  {'min_date': orig_year_start,
                   'max_date': orig_year_end},
              'keyword_fields': ['orig_place.cert',
                                 'person.role',
                                 'person.identifier',
                                 'autocomplete_person.role',
                                 'autocomplete_person.identifier',
                                 'autocomplete_orig_place.cert'],
              'simple_q_fields':
                  ['identifier',
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
                bool_clauses.append({'span_near': {'clauses': list(clause), 'slop': 0, 'in_order': False}})
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
    return search['hits']['hits'], search['hits']['total'], search['aggregations']
