from app import app
from lxml import etree
from glob import glob
import os
from flask import render_template
import re

dirname = os.path.dirname(__file__)

namespaces = {'tei': 'http://www.tei-c.org/ns/1.0'}
xmls = glob(os.path.join(dirname, '../xmls/*.xml'))
name_dict = dict()
for x in xmls:
    xml = etree.parse(x)
    for t in xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:titleStmt/tei:title/text()', namespaces=namespaces):
        name_dict[os.path.basename(x)] = t

language_mapping = {'la': 'Latein'}

material_mapping = {'perg': 'Pergament'}

@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html')


@app.route('/handschriften')
def handschriften():
    return render_template('handschriften.html', title='Handschriftenliste', handschriften_dict=name_dict)


@app.route('/handschrift/<manuscript>')
def handschrift(manuscript: str):
    metadata = dict()
    xml = etree.parse(os.path.join(dirname, '../xmls', manuscript))
    metadata['old_sigs'] = list()
    for alt_id in xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:msIdentifier/tei:altIdentifier',
                            namespaces=namespaces):
        metadata['old_sigs'].append('{} {}'.format(alt_id.get('source'), ' '.join(alt_id.xpath('tei:idno/text()', namespaces=namespaces))))
    metadata['contents'] = []
    for item in xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:msContents/tei:msItem',
                          namespaces=namespaces):
        item_dict = {'class': '', 'author': '', 'title': '', 'language': '', 'locus': '', 'parts': []}
        if item.get('class'):
            item_dict['class'] = item.get('class')
        item_dict['author'] = ', '.join(item.xpath('tei:author/text()', namespaces=namespaces))
        item_dict['title'] = ', '.join(item.xpath('tei:title/text()', namespaces=namespaces))
        if item.xpath('tei:textLang', namespaces=namespaces):
            for x in item.xpath('tei:textLang', namespaces=namespaces):
                item_dict['language'] = ', '.join([language_mapping.get(x.get('mainLang'), x.get('mainLang'))])
        loci = []
        for l in item.xpath('tei:locus', namespaces=namespaces):
            if l.get('from'):
                loci.append('{}{}'.format(l.get('from'), '-' + l.get('to') if l.get('to') else ''))
            else:
                loci.append(l.get('n', ''))
        item_dict['locus'] = '/'.join(loci)
        for sub_item in item.xpath('tei:msItem', namespaces=namespaces):
            sub_item_info = {'title': '', 'locus': ''}
            sub_item_info['title'] = ', '.join(sub_item.xpath('tei:title/text()', namespaces=namespaces))
            sub_loci = []
            for l in sub_item.xpath('tei:locus', namespaces=namespaces):
                if l.get('from'):
                    sub_loci.append('{}{}'.format(l.get('from'), '-' + l.get('to') if l.get('to') else ''))
                else:
                    sub_loci.append(l.get('n', ''))
            sub_item_info['locus'] = '/'.join(sub_loci)
            item_dict['parts'].append(sub_item_info)
        metadata['contents'].append(item_dict)
    metadata['origin'] = {'place': [], 'date': [], 'commentary': []}
    places = xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:history/tei:origin/tei:p/tei:origPlace',
                       namespaces=namespaces)
    dates = xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:history/tei:origin/tei:p/tei:origDate',
                      namespaces=namespaces)
    for p in places:
        if p.xpath('.//text()'):
            metadata['origin']['place'].append('{}{}{}'.format(' '.join(p.xpath('.//text()')), '?' if p.get('cert') == 'low' else '',
                                                               ' (' + p.get('source').upper().replace(' ', '; ') + ')' if
                                                               p.get('source') else ''))
    for d in dates:
        if d.xpath('.//text()'):
            metadata['origin']['date'].append('{}{}{}'.format(' '.join(d.xpath('.//text()')), '?' if d.get('cert') == 'low' else '',
                                                              ' (' + d.get('source').upper().replace(' ', '; ') + ')' if
                                                              d.get('source') else ''))
    for c in xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:history/tei:origin/tei:note/text()',
                       namespaces=namespaces):
        metadata['origin']['commentary'].append(c)
    metadata['layout_notes'] = []
    metadata['condition'] = []
    for obj_desc in xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:physDesc/tei:objectDesc',
                              namespaces=namespaces):
        metadata['obj_form'] = obj_desc.get('form')
        for sup_desc in obj_desc.xpath('tei:supportDesc', namespaces=namespaces):
            metadata['obj_material'] = material_mapping.get(sup_desc.get('material'), sup_desc.get('material'))
            for extent in sup_desc.xpath('tei:extent', namespaces=namespaces):
                metadata['num_pages'] = extent.get('n')
                for dimension in extent.xpath('tei:dimensions', namespaces=namespaces):
                    dim_unit = dimension.get('unit')
                    dim_height = dimension.xpath('tei:height/@n', namespaces=namespaces)
                    dim_width = dimension.xpath('tei:width/@n', namespaces=namespaces)
                    if dimension.get('type') == 'leaf':
                        metadata['page_size'] = '{} x {}'.format(dim_height[0] + ' ' +  dim_unit if dim_height else '',
                                                                 dim_width[0] + ' ' + dim_unit if dim_width else '')
                    if dimension.get('type') == 'written':
                        metadata['dim_written'] = '{} x {}'.format(dim_height[0] + ' ' + dim_unit if dim_height else '',
                                                                   dim_width[0] + ' ' + dim_unit if dim_width else '')
            for condition in sup_desc.xpath('tei:condition', namespaces= namespaces):
                if condition.text:
                    metadata['condition'].append('{}{}'.format(condition.text,
                                                               ' (' + condition.get('source').upper().replace(' ', '; ') + ')' if
                                                               condition.get('source') else ''))
        for lay_desc in obj_desc.xpath('tei:layoutDesc', namespaces=namespaces):
            for layout in lay_desc.xpath('tei:layout', namespaces=namespaces):
                if layout.get('columns'):
                    if layout.text:
                        metadata['num_columns'] = layout.text
                    else:
                        metadata['num_columns'] = layout.get('columns')
                elif layout.get('writtenLines'):
                    if layout.text:
                        metadata['written_lines'] = layout.text
                    else:
                        metadata['written_lines'] = layout.get('writtenLines')
                else:
                    if layout.text:
                        metadata['layout_notes'].append('{}{}'.format(layout.text,
                                                                      ' (' + layout.get('source').upper().replace(' ', '; ') + ')' if
                                                                      layout.get('source') else ''))
    metadata['script_desc'] = []
    for scr_desc in xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:physDesc/tei:scriptDesc/tei:p',
                              namespaces=namespaces):
        if scr_desc.text:
            metadata['script_desc'].append('{}{}'.format(scr_desc.text,
                                                         ' (' + scr_desc.get('source').upper().replace(' ', '; ') + ')' if
                                                         scr_desc.get('source') else ''))
    metadata['hand_desc'] = []
    for hand_desc in xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:physDesc/tei:handDesc/tei:p',
                              namespaces=namespaces):
        metadata['hand_desc'].append('{}{}'.format(hand_desc.text,
                                                   ' (' + hand_desc.get('source').upper().replace(' ', '; ') + ')'
                                                   if hand_desc.get('source') else ''))
    metadata['marginal'] = []
    for adds in xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:physDesc/tei:musicNotation/tei:p',
                           namespaces=namespaces):
        if adds.xpath('tei:locus/@n', namespaces=namespaces) and adds.xpath('tei:locus/@n', namespaces=namespaces)[0]:
            metadata['marginal'].append('{}{}{}'.format('fol. ' + adds.xpath('tei:locus/@n', namespaces=namespaces)[0] + ' ' if
                                                        adds.xpath('tei:locus/@n', namespaces=namespaces) else '',
                                                        ''.join(adds.xpath('.//text()')),
                                                        ' (' + adds.get('source').upper().replace(' ', '; ') + ')' if
                                                        adds.get('source') else ''))
    metadata['exlibris'] = []
    for adds in xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:physDesc/tei:additions/tei:p',
                          namespaces=namespaces):
        add_locus = ''
        if adds.xpath('tei:locus/@n', namespaces=namespaces) and adds.xpath('tei:locus/@n', namespaces=namespaces)[0]:
            add_locus = 'fol. ' + adds.xpath('tei:locus/@n', namespaces=namespaces)[0] + ' '
        if adds.get('n') == 'Exlibris':
            metadata['exlibris'].append('{}{}'.format(add_locus, ''.join(adds.xpath('.//text()'))))
        else:
            children = [etree.tostring(x) for x in adds.iterchildren() if x.text]
            metadata['marginal'].append('{}{}{}'.format(add_locus, ''.join(adds.xpath('.//text()')),
                                                      ' (' + adds.get('source').upper().replace(' ', '; ') + ')' if
                                                      adds.get('source') else ''))
    metadata['provenance'] = []
    metadata['provenance_notes'] = []
    for provenance in xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:history/tei:provenance',
                                namespaces=namespaces):
        if provenance.xpath('.//text()'):
            if provenance.get('type') == 'Provenance':
                metadata['provenance'].append(''.join(provenance.xpath('.//text()')))
            else:
                metadata['provenance_notes'].append('{}{}'.format(''.join(provenance.xpath('.//text()')),
                                                                  ' (' + provenance.get('source').upper().replace(' ', '; ') + ')' if
                                                                  provenance.get('source') else ''))
    metadata['bibliography'] = []
    metadata['online_description'] = []
    metadata['digital_representations'] = []
    for bibl in xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:additional//tei:bibl',
                          namespaces=namespaces):
        if 'Online Beschreibung' in ''.join(bibl.xpath('.//text()')):
            for b in bibl.xpath('tei:idno/text()', namespaces=namespaces):
                if b.startswith('http'):
                    text = '<a href="{link}" target="_blank">{link}</a>'.format(link=b)
                else:
                    text = b
                metadata['online_description'].append(text)
        elif 'Digitalisat' in ''.join(bibl.xpath('.//text()')):
            texts = []
            for b in bibl.xpath('tei:idno/text()', namespaces=namespaces):
                if b.startswith('http'):
                    texts.append('<a href="{link}" target="_blank">{link}</a>'.format(link=b))
                else:
                    texts.append(b)
            metadata['digital_representations'].append('; '.join(texts))
        else:
            title = bibl.xpath('tei:idno/text()', namespaces=namespaces)[0].upper() if bibl.xpath('tei:idno/text()', namespaces=namespaces) else ''
            pages = ''
            if bibl.xpath('tei:biblScope/@n', namespaces=namespaces):
                pages = bibl.xpath('tei:biblScope/@n', namespaces=namespaces)[0].replace(' ', '-')
            elif bibl.xpath('tei:biblScope/@from', namespaces=namespaces):
                pages = bibl.xpath('tei:biblScope/@from', namespaces=namespaces)[0] + '-' + bibl.xpath('tei:biblScope/@to', namespaces=namespaces)[0]
            metadata['bibliography'].append('{}{}'.format(title, ', S. ' + pages if pages else ''))
    metadata['binding'] = []
    for bind in xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:physDesc/tei:bindingDesc',
                          namespaces=namespaces):
        binding_text = ' '.join(bind.xpath('.//text()')).strip()
        if binding_text:
            metadata['binding'].append(re.sub(r'\s+', ' ', binding_text))
    return render_template('handschrift.html', title=name_dict[manuscript], m_d=metadata)
