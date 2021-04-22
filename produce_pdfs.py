


def download_search_results(title: str='', m_d: dict=None):
    resp = list()
    arg_list = list()
    special_day_dict = dict([('', ''),
                             ('Easter', _('Ostern')),
                             ('Lent', _('Fastenzeit')),
                             ('Pentecost', _('Pfingsten')),
                             ('Sunday', _('Sonntag')),
                             ('Monday', _('Montag')),
                             ('Tuesday', _('Dienstag')),
                             ('Wednesday', _('Mittwoch')),
                             ('Thursday', _('Donnerstag')),
                             ('Friday', _('Freitag')),
                             ('Saturday', _('Samstag'))])
    search_arg_mapping = [('q', _('Suchbegriff')), ('lemma_search', _('Lemma?')),
                          ('regest_q', _('Regesten Suchbegriff')), ('fuzziness', _('Unschärfegrad')),
                          ('slop', _('Suchradius')), ('in_order', _('Wortreihenfolge beachten?')), ('year', _('Jahr')),
                          ('month', _('Monat')), ('day', _('Tag')), ('year_start', _('Anfangsjahr')),
                          ('month_start', _('Anfangsmonat')), ('day_start', _('Anfangstag')), ('year_end', _('Endjahr')),
                          ('month_end', _('Endmonat')), ('day_end', _('Endtag')), ('date_plus_minus', _('Datum Plus-Minus')),
                          ('exclusive_date_range', _('Exklusiv')), ('composition_place', _('Ausstellungsort')),
                          ('special_days', _('Besondere Tage')), ('corpus', _('Corpora')), ('formulaic_parts', _('Urkundenteile'))]
    search_value_dict = {'False': _('Nein'), 'True': _('Ja'), False: _('Nein'), True: _('Ja')}
    for arg, s in search_arg_mapping:
        if arg in session['previous_search_args']:
            value = search_value_dict.get(session['previous_search_args'][arg], session['previous_search_args'][arg])
        else:
            value = ''
        if arg == 'corpus':
            value = ' - '.join([CORP_MAP[x] for x in value.split('+')])
        if arg == 'special_days':
            value = ' - '.join([special_day_dict[x] for x in value.split('+')])
        if arg == 'formulaic_parts':
            value = ' - '.join([x for x in value.split('+')])
        arg_list.append('<b>{}</b>: {}'.format(s, value if value != '0' else ''))
    prev_args = session['previous_search_args']
    if prev_args.get('formulaic_parts', None):
        ids = []
        for list_index, hit in enumerate(session['previous_search']):
            sents = []
            if 'highlight' in hit:
                for highlight in hit['highlight']:
                    sents.append(re.sub(r'(</?)strong(>)', r'\1b\2', str(highlight)))
            regest_sents = []
            if 'regest_sents' in hit:
                for s in hit['regest_sents']:
                    regest_sents.append(re.sub(r'(</?)strong(>)', r'\1b\2', str(s)))
            ids.append({'id': hit['id'],
                        'info': hit['info'],
                        'sents': sents,
                        'title': hit['info']['title'],
                        'regest_sents': regest_sents})
            current_app.redis.set(download_id, str(floor((list_index / len(session['previous_search'])) * 100)) + '%')
        current_app.redis.setex(download_id, 60, '99%')
    else:
        try:
            ids = session['previous_search']
        # This finally statement makes sure that the JS function to get the progress halts on an error.
        finally:
            current_app.redis.setex(download_id, 60, '99%')
    for d in ids:
        r = {'title': d['title'], 'sents': [], 'regest_sents': []}
        if 'sents' in d and d['sents'] != []:
            r['sents'] = ['- {}'.format(re.sub(r'(?:</small>)?<strong>(.*?)</strong>(?:<small>)?', r'<b>\1</b>',
                                               str(s)))
                          for s in d['sents']]
        if 'regest_sents' in d and d['regest_sents'] != []:
            r['regest_sents'] = ['<u>' + _('Aus dem Regest') + '</u>']
            r['regest_sents'] += ['- {}'.format(re.sub(r'(?:</small>)?<strong>(.*?)</strong>(?:<small>)?',
                                                       r'<b>\1</b>',
                                                       str(s)))
                                  for s in d['regest_sents']]
        resp.append(r)
    pdf_buffer = BytesIO()
    description = 'Formulae-Litterae-Chartae Suchergebnisse ({})'.format(date.today().isoformat())
    my_doc = SimpleDocTemplate(pdf_buffer, title=description)
    sample_style_sheet = getSampleStyleSheet()
    flowables = list([Paragraph(_('Suchparameter'), sample_style_sheet['Heading3'])])
    for a in arg_list:
        flowables.append(Paragraph(a, sample_style_sheet['Normal']))
    flowables.append(Paragraph(_('Suchergebnisse'), sample_style_sheet['Heading3']))
    for p in resp:
        flowables.append(Paragraph(p['title'], sample_style_sheet['Heading4']))
        for sentence in p['sents']:
            flowables.append(Paragraph(sentence, sample_style_sheet['Normal']))
        for r_sentence in p['regest_sents']:
            flowables.append(Paragraph(r_sentence, sample_style_sheet['Normal']))
    my_doc.build(flowables)
    pdf_value = pdf_buffer.getvalue()
    pdf_buffer.close()
    session.pop(download_id, None)
    return Response(pdf_value, mimetype='application/pdf',
                    headers={'Content-Disposition': 'attachment;filename={}.pdf'.format(description.replace(' ', '_'))})
