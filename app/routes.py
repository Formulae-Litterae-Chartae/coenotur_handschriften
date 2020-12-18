from app import app
from lxml import etree
from glob import glob
import os
from flask import render_template

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
    return "Hello, World!"


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
    metadata['contents'] = {'class': [], 'author': [], 'title': [], 'language': []}
    for item in xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:msContents/tei:msItem',
                          namespaces=namespaces):
        metadata['contents']['class'].append(item.get('class'))
        metadata['contents']['author'].append(', '.join(item.xpath('tei:author/text()', namespaces=namespaces)))
        metadata['contents']['title'].append(', '.join(item.xpath('tei:title/text()', namespaces=namespaces)))
        metadata['contents']['language'].append(', '.join([language_mapping.get(x.get('mainLang'), x.get('mainLang'))
                                                           for x in item.xpath('tei:textLang', namespaces=namespaces)]))
    metadata['origin'] = {'place': [], 'date': [], 'commentary': []}
    places = xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:history/tei:origin/tei:p/tei:origPlace',
                       namespaces=namespaces)
    dates = xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:history/tei:origin/tei:p/tei:origDate',
                      namespaces=namespaces)
    for p in places:
        metadata['origin']['place'].append('{}{}{}'.format(p.text, '?' if p.get('cert') == 'low' else '',
                                                           ' (' + p.get('source').upper().replace(' ', '; ') + ')' if
                                                           len(places) > 1 and p.get('source') else ''))
    for d in dates:
        metadata['origin']['date'].append('{}{}{}'.format(d.text, '?' if d.get('cert') == 'low' else '',
                                                          ' (' + d.get('source').upper().replace(' ', '; ') + ')' if
                                                          len(dates) > 1 and d.get('source') else ''))
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
                        metadata['page_size'] = '{} x {}'.format(dim_height[0] + dim_unit if dim_height else '',
                                                                 dim_width[0] + dim_unit if dim_width else '')
                    if dimension.get('type') == 'written':
                        metadata['dim_written'] = '{} x {}'.format(dim_height[0] + dim_unit if dim_height else '',
                                                                   dim_width[0] + dim_unit if dim_width else '')
            for condition in sup_desc.xpath('tei:condition', namespaces= namespaces):
                if condition.text:
                    metadata['condition'].append('{}{}'.format(condition.text,
                                                               ' (' + condition.get('source').upper().replace(' ', '; ') + ')' if
                                                               condition.get('source') else ''))
        for lay_desc in obj_desc.xpath('tei:layoutDesc', namespaces=namespaces):
            for layout in lay_desc.xpath('tei:layout', namespaces=namespaces):
                if layout.get('columns'):
                    metadata['num_columns'] = layout.get('columns')
                elif layout.get('writtenLines'):
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
    metadata['additions'] = []
    for music in xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:physDesc/tei:musicNotation/tei:p',
                           namespaces=namespaces):
        metadata['additions'].append('{}{}'.format('fol. ' + music.xpath('tei:locus/@n', namespaces=namespaces)[0] + ' ' if
                                                   music.xpath('tei:locus/@n', namespaces=namespaces) else '',
                                                   ''.join(music.xpath('.//text()'))))
    metadata['marginal'] = []
    metadata['exlibris'] = []
    for adds in xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:physDesc/tei:additions/tei:p',
                          namespaces=namespaces):
        if adds.get('n') == 'Exlibris':
            metadata['exlibris'].append('{}{}'.format('fol. ' + adds.xpath('tei:locus/@n', namespaces=namespaces)[0] + ' ' if
                                                      adds.xpath('tei:locus/@n', namespaces=namespaces) else '',
                                                      ''.join(adds.xpath('.//text()'))))
        else:
            metadata['marginal'].append('{}{}{}'.format('fol. ' + adds.xpath('tei:locus/@n', namespaces=namespaces)[0] + ' ' if
                                                      adds.xpath('tei:locus/@n', namespaces=namespaces) else '',
                                                      ''.join(adds.xpath('.//text()')),
                                                      ' (' + adds.get('source').upper().replace(' ', '; ') + ')' if
                                                      adds.get('source') else ''))
    metadata['provenance'] = []
    metadata['provenance_notes'] = []
    for provenance in xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:history/tei:provenance',
                                namespaces=namespaces):
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
            metadata['online_description'].append(bibl.xpath('tei:idno/text()', namespaces=namespaces)[0] if
                                                  bibl.xpath('tei:idno/text()', namespaces=namespaces) else '')
        elif 'Digitalisat' in ''.join(bibl.xpath('.//text()')):
            metadata['digital_representations'].append('; '.join(bibl.xpath('tei:idno/text()', namespaces=namespaces)))
        else:
            metadata['bibliography'].append('{}, {}'.format(bibl.xpath('tei:idno/text()', namespaces=namespaces)[0].upper() if
                                            bibl.xpath('tei:idno/text()', namespaces=namespaces) else '',
                                            bibl.xpath('tei:biblScope/@n', namespaces=namespaces)[0].replace(' ', '-') if
                                            bibl.xpath('tei:biblScope', namespaces=namespaces) else ''))
    return render_template('handschrift.html', title=name_dict[manuscript], m_d=metadata)
