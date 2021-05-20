from lxml import etree
import os
from flask import render_template, g, current_app
from flask_login import login_required
import re
from app.main import bp
from app.search.forms import SearchForm

language_mapping = {'la': 'Latein'}

material_mapping = {'perg': 'Pergament'}

style_span_mapping = {'lat': '<em>{}</em>'}

cert_dict = {'high': 'hoch', 'medium': 'mittel', 'low': 'niedrig'}


def insert_style_spans(el: etree._Element) -> list:
    """ Checks all text() descendents to see if they need special styling

    :param el:
    :return:
    """
    text_parts = []
    for t in el.xpath('.//text()'):
        par = t.getparent()
        if par.tag == '{http://www.tei-c.org/ns/1.0}seg' and par.get('type') in style_span_mapping and t.is_text:
            text_parts.append(style_span_mapping[par.get('type')].format(t))
        else:
            text_parts.append(t)
    return text_parts


@bp.before_app_request
def before_request():
    g.search_form = SearchForm()


@bp.route('/')
@bp.route('/index')
@login_required
def index():
    return render_template('index.html')


@bp.route('/handschriften')
@login_required
def handschriften():
    return render_template('handschriften.html', title='Handschriftenliste', handschriften_dict=current_app.manuscript_list)


@bp.route('/handschrift/<manuscript>')
@login_required
def handschrift(manuscript: str):
    metadata = dict()
    xml = etree.parse(os.path.join(current_app.config['XML_LOCATION'], manuscript))
    metadata['old_sigs'] = list()
    for alt_id in xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:msIdentifier/tei:altIdentifier',
                            namespaces=current_app.namespaces):
        metadata['old_sigs'].append('{} {}'.format(alt_id.get('source'), ' '.join(alt_id.xpath('tei:idno/text()', namespaces=current_app.namespaces))))
    metadata['contents'] = []
    for item in xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:msContents/tei:msItem',
                          namespaces=current_app.namespaces):
        item_dict = {'class': '', 'author': '', 'title': '', 'language': '', 'locus': '', 'parts': []}
        if item.get('class'):
            item_dict['class'] = item.get('class')
        item_dict['author'] = ', '.join(item.xpath('tei:author/text()', namespaces=current_app.namespaces))
        item_dict['title'] = ', '.join(item.xpath('tei:title/text()', namespaces=current_app.namespaces))
        if item.xpath('tei:textLang', namespaces=current_app.namespaces):
            for x in item.xpath('tei:textLang', namespaces=current_app.namespaces):
                item_dict['language'] = ', '.join([language_mapping.get(x.get('mainLang'), x.get('mainLang'))])
        loci = []
        for l in item.xpath('tei:locus', namespaces=current_app.namespaces):
            if l.get('from'):
                loci.append('{}{}'.format(l.get('from'), '-' + l.get('to') if l.get('to') else ''))
            else:
                loci.append(l.get('n', ''))
        item_dict['locus'] = '/'.join(loci)
        for sub_item in item.xpath('tei:msItem', namespaces=current_app.namespaces):
            sub_item_info = {'title': '', 'locus': '', 'author': '', 'notes': ''}
            sub_item_info['title'] = ', '.join(sub_item.xpath('tei:title/text()', namespaces=current_app.namespaces))
            sub_loci = []
            sub_item_info['author'] = ', '.join(sub_item.xpath('tei:author/text()', namespaces=current_app.namespaces))
            sub_item_info['notes'] = '; '.join(sub_item.xpath('tei:note/text()', namespaces=current_app.namespaces))
            for l in sub_item.xpath('tei:locus', namespaces=current_app.namespaces):
                if l.get('from'):
                    sub_loci.append('{}{}'.format(l.get('from'), '-' + l.get('to') if l.get('to') else ''))
                else:
                    sub_loci.append(l.get('n', ''))
            sub_item_info['locus'] = '/'.join(sub_loci)
            item_dict['parts'].append(sub_item_info)
        if not item_dict['parts']:
            item_dict.pop('parts')
        metadata['contents'].append(item_dict)
    metadata['origin'] = {'place': [], 'date': [], 'commentary': []}
    places = xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:history/tei:origin/tei:p/tei:origPlace',
                       namespaces=current_app.namespaces)
    dates = xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:history/tei:origin/tei:p/tei:origDate',
                      namespaces=current_app.namespaces)
    for p in places:
        if p.xpath('.//text()'):
            cert_symbol = ''
            if p.get('cert'):
                cert_symbol = ' <span class="cert-{}" title="Sicherheit: {}">&#11044;</span>'.format(p.get('cert'), cert_dict.get(p.get('cert'), '?'))
            metadata['origin']['place'].append('{}{}{}'.format(''.join(insert_style_spans(p)), cert_symbol,
                                                               ' (' + p.get('source').upper().replace(' ', '; ').replace('_', ' ') + ')' if
                                                               p.get('source') else ''))
    for d in dates:
        if d.xpath('.//text()'):
            cert_symbol = ''
            if d.get('cert'):
                cert_symbol = ' <span class="cert-{}" title="Sicherheit: {}">&#11044;</span>'.format(d.get('cert'), cert_dict.get(d.get('cert'), '?'))
            metadata['origin']['date'].append('{}{}{}'.format(''.join(insert_style_spans(d)), cert_symbol,
                                                              ' (' + d.get('source').upper().replace(' ', '; ').replace('_', ' ') + ')' if
                                                              d.get('source') else ''))
    for c in xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:history/tei:origin/tei:note',
                       namespaces=current_app.namespaces):
        c_text = ''.join(c.xpath('.//text()'))
        end_symbol = ''
        if c_text.strip().endswith('.'):
            end_symbol = '.'
        metadata['origin']['commentary'].append('{}{}{}'.format(c_text.strip('. \n'),
                                                                ' (' + c.get('source').upper().replace(' ', '; ').replace('_', ' ') + ')' if
                                                                c.get('source') else '',
                                                                end_symbol))
    metadata['layout_notes'] = []
    metadata['condition'] = []
    for obj_desc in xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:physDesc/tei:objectDesc',
                              namespaces=current_app.namespaces):
        metadata['obj_form'] = obj_desc.get('form')
        for sup_desc in obj_desc.xpath('tei:supportDesc', namespaces=current_app.namespaces):
            metadata['obj_material'] = material_mapping.get(sup_desc.get('material'), sup_desc.get('material'))
            for extent in sup_desc.xpath('tei:extent', namespaces=current_app.namespaces):
                metadata['num_pages'] = extent.text.strip() if extent.text.strip() else extent.get('n')
                for dimension in extent.xpath('tei:dimensions', namespaces=current_app.namespaces):
                    dim_unit = dimension.get('unit')
                    height_element = dimension.xpath('tei:height', namespaces=current_app.namespaces)
                    width_element = dimension.xpath('tei:width', namespaces=current_app.namespaces)
                    dim_height = ''
                    dim_width = ''
                    if len(height_element) > 0:
                        if height_element[0].text and height_element[0].text.strip():
                            dim_height = height_element[0].text.strip()
                        elif height_element[0].get('n'):
                            dim_height = height_element[0].get('n').replace('.', ',') + ' ' + dim_unit
                    if len(width_element) > 0:
                        if width_element[0].text and width_element[0].text.strip():
                            dim_width = width_element[0].text.strip()
                        elif width_element[0].get('n'):
                            dim_width = width_element[0].get('n').replace('.', ',') + ' ' + dim_unit
                    if dimension.get('type') == 'leaf':
                        metadata['page_size'] = '{} x {}'.format(dim_height, dim_width)
                    if dimension.get('type') == 'written':
                        metadata['dim_written'] = '{} x {}'.format(dim_height, dim_width)
            for condition in sup_desc.xpath('tei:condition', namespaces=current_app.namespaces):
                condition_text = ''.join(condition.xpath('.//text()'))
                if condition_text:
                    end_symbol = ''
                    if condition_text.strip().endswith('.'):
                        end_symbol = '.'
                    metadata['condition'].append('{}{}{}'.format(condition_text.strip('. \n'),
                                                                 ' (' + condition.get('source').upper().replace(' ', '; ').replace('_', ' ') + ')' if
                                                                 condition.get('source') else '',
                                                                 end_symbol))
        for lay_desc in obj_desc.xpath('tei:layoutDesc', namespaces=current_app.namespaces):
            for layout in lay_desc.xpath('tei:layout', namespaces=current_app.namespaces):
                layout_text = ''.join(layout.xpath('.//text()'))
                if layout.get('columns'):
                    if layout_text:
                        metadata['num_columns'] = layout_text
                    else:
                        metadata['num_columns'] = layout.get('columns')
                elif layout.get('writtenLines'):
                    if layout_text:
                        metadata['written_lines'] = layout_text
                    else:
                        metadata['written_lines'] = layout.get('writtenLines')
                else:
                    if layout_text:
                        end_symbol = ''
                        if layout_text.strip().endswith('.'):
                            end_symbol = '.'
                        metadata['layout_notes'].append('{}{}{}'.format(layout_text.strip('. \n'),
                                                                        ' (' + layout.get('source').upper().replace(' ', '; ').replace('_', ' ') + ')' if
                                                                        layout.get('source') else '',
                                                                        end_symbol))
    metadata['script_desc'] = []
    for scr_desc in xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:physDesc/tei:scriptDesc',
                              namespaces=current_app.namespaces):
        for note in scr_desc.xpath('./tei:p|./tei:scriptNote', namespaces=current_app.namespaces):
            scr_desc_text = ''.join(note.xpath('.//text()'))
            if scr_desc_text:
                end_symbol = ''
                if scr_desc_text.strip().endswith('.'):
                    end_symbol = '.'
                metadata['script_desc'].append('{}{}{}'.format(scr_desc_text.strip('. \n'),
                                                               ' (' + note.get('source').upper().replace(' ', '; ').replace('_', ' ') + ')' if
                                                               note.get('source') else '',
                                                               end_symbol))
    metadata['hand_desc'] = []
    for hand_desc in xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:physDesc/tei:handDesc',
                               namespaces=current_app.namespaces):
        for note in hand_desc.xpath('./tei:p|./tei:handNote', namespaces=current_app.namespaces):
            hand_desc_text = ''.join(note.xpath('.//text()'))
            if hand_desc_text:
                end_symbol = ''
                if hand_desc_text.strip().endswith('.'):
                    end_symbol = '.'
                metadata['hand_desc'].append('{}{}{}'.format(hand_desc_text.strip('. \n'),
                                                             ' (' + note.get('source').upper().replace(' ', '; ').replace('_', ' ') + ')'
                                                             if note.get('source') else '',
                                                             end_symbol))
    metadata['neumen'] = []
    for adds in xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:physDesc/tei:musicNotation/tei:p',
                          namespaces=current_app.namespaces):
        neumen_locus = ''
        neumen_text = ''.join(insert_style_spans(adds))
        end_symbol = ''
        if adds.xpath('tei:locus/@n', namespaces=current_app.namespaces) and adds.xpath('tei:locus/@n', namespaces=current_app.namespaces)[0]:
            neumen_locus = adds.xpath('tei:locus/@n', namespaces=current_app.namespaces)[0]
        if neumen_text.strip().endswith('.'):
            end_symbol = '.'
        metadata['neumen'].append('{}{}{}{}'.format('fol. ' + neumen_locus + ' - ' if neumen_locus else '',
                                                    neumen_text.strip('. \n'),
                                                    ' (' + adds.get('source').upper().replace(' ', '; ').replace('_', ' ') + ')' if
                                                    adds.get('source') else '',
                                                    end_symbol))
    metadata['exlibris'] = []
    metadata['tironoten'] = []
    metadata['marginal'] = []
    for adds in xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:physDesc/tei:additions/tei:p',
                          namespaces=current_app.namespaces):
        add_locus = ''
        marked_up_text = ''.join(insert_style_spans(adds))
        if adds.xpath('tei:locus/@n', namespaces=current_app.namespaces) and adds.xpath('tei:locus/@n', namespaces=current_app.namespaces)[0]:
            add_locus = 'fol. ' + adds.xpath('tei:locus/@n', namespaces=current_app.namespaces)[0] + ' '
        if adds.get('n') == 'Exlibris':
            if add_locus or marked_up_text:
                metadata['exlibris'].append('{}{}'.format(add_locus, marked_up_text))
        else:
            m_d_target = 'marginal'
            if adds.get('n') == 'tironischen Note':
                m_d_target = 'tironoten'
            if add_locus or marked_up_text:
                end_symbol = ''
                if marked_up_text.strip().endswith('.'):
                    end_symbol = '.'
                metadata[m_d_target].append('{}{}{}{}'.format(add_locus, marked_up_text,
                                                              ' (' + adds.get('source').upper().replace(' ', '; ').replace('_', ' ') + ')' if
                                                              adds.get('source') else '',
                                                              end_symbol))
    metadata['provenance'] = []
    metadata['provenance_notes'] = []
    for provenance in xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:history/tei:provenance',
                                namespaces=current_app.namespaces):
        if provenance.xpath('.//text()'):
            prov_text = ''.join(insert_style_spans(provenance))
            if provenance.get('type') == 'Provenance':
                metadata['provenance'].append(prov_text)
            else:
                end_symbol = ''
                if prov_text.strip().endswith('.'):
                    end_symbol = '.'
                metadata['provenance_notes'].append('{}{}{}'.format(prov_text.strip('. \n'),
                                                                    ' (' + provenance.get('source').upper().replace(' ', '; ').replace('_', ' ') + ')' if
                                                                    provenance.get('source') else '',
                                                                    end_symbol))
    metadata['bibliography'] = dict()
    metadata['online_description'] = []
    metadata['digital_representations'] = []
    for bibl in xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:additional//tei:bibl',
                          namespaces=current_app.namespaces):
        if 'Online Beschreibung' in ''.join(bibl.xpath('.//text()')):
            for b in bibl.xpath('tei:idno/text()', namespaces=current_app.namespaces):
                if b.startswith('http'):
                    text = '<a href="{link}" target="_blank">{link}</a>'.format(link=b)
                else:
                    text = b
                metadata['online_description'].append(text)
        elif 'Digitalisat' in ''.join(bibl.xpath('.//text()')):
            texts = []
            for b in bibl.xpath('tei:idno/text()', namespaces=current_app.namespaces):
                if b.startswith('http'):
                    texts.append('<a href="{link}" target="_blank">{link}</a>'.format(link=b))
                else:
                    texts.append(b)
            if texts:
                metadata['digital_representations'].append('; '.join(texts))
        else:
            title = bibl.xpath('tei:idno/text()', namespaces=current_app.namespaces)[0].upper() if bibl.xpath('tei:idno/text()', namespaces=current_app.namespaces) else ''
            pages = ''
            if bibl.xpath('tei:biblScope/@n', namespaces=current_app.namespaces):
                if bibl.xpath('tei:biblScope/@unit="pp"', namespaces=current_app.namespaces):
                    pages = 'S. ' + bibl.xpath('tei:biblScope/@n', namespaces=current_app.namespaces)[0].replace(' ', '-')
                else:
                    pages = bibl.xpath('tei:biblScope/@n', namespaces=current_app.namespaces)[0].replace(' ', '-')
            elif bibl.xpath('tei:biblScope/@from', namespaces=current_app.namespaces):
                pages = 'S. ' + bibl.xpath('tei:biblScope/@from', namespaces=current_app.namespaces)[0] + '-' + bibl.xpath('tei:biblScope/@to', namespaces=current_app.namespaces)[0]
            elif bibl.xpath('tei:biblScope//text()', namespaces=current_app.namespaces):
                pages = re.sub(r'\s+', ' ', ' '.join(insert_style_spans(bibl.xpath('tei:biblScope', namespaces=current_app.namespaces)[0])))
            if title in metadata['bibliography'] and metadata['bibliography'][title] != []:
                if pages:
                    metadata['bibliography'][title].append(re.sub(r'^S\. ', '', pages.strip()))
            else:
                if pages:
                    metadata['bibliography'][title] = [pages.strip()]
                else:
                    metadata['bibliography'][title] = []
            
    metadata['binding'] = []
    for bind in xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:physDesc/tei:bindingDesc',
                          namespaces=current_app.namespaces):
        binding_text = ' '.join(insert_style_spans(bind)).strip()
        if binding_text:
            metadata['binding'].append(re.sub(r'\s+', ' ', binding_text))
    metadata['general_notes'] = []
    for note in xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:notesStmt/tei:note',
                          namespaces=current_app.namespaces):
        source = note.get('source')
        if not source:
            for p_tag in note.xpath('./tei:p/@source', namespaces=current_app.namespaces):
                if p_tag:
                    source = p_tag
        if note.xpath('.//text()'):
            end_symbol = ''
            note_text = ' '.join(insert_style_spans(note))
            if note_text.strip().endswith('.'):
                end_symbol = '.'
            metadata['general_notes'].append('{}{}{}'.format(re.sub(r'\s+', ' ', note_text.strip('. \n')),
                                                             ' ({})'.format(source.upper().replace('_', ' ')) if
                                                             source else '',
                                                             end_symbol))
    metadata['illuminations'] = []
    for deco in xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:physDesc/tei:decoDesc/tei:decoNote',
                          namespaces=current_app.namespaces):
        locus = []
        deco_text = ''.join(deco.xpath('.//text()')).rstrip()
        source = deco.get('source')
        if not source:
            for p_tag in deco.xpath('./tei:p/@source', namespaces=current_app.namespaces):
                if p_tag:
                    source = p_tag
        for l in deco.xpath('tei:locus', namespaces=current_app.namespaces):
            if l.get('n'):
                locus.append(l.get('n'))
            elif l.get('from'):
                locus.append('{}{}'.format(l.get('from'), '-' + l.get('to') if l.get('to') else ''))
        if locus or deco_text:
            end_symbol = ''
            if deco_text.strip().endswith('.'):
                end_symbol = '.'
            metadata['illuminations'].append('- {}{}{}{}'.format('fol. ' + ', '.join(locus) + ' - ' if locus else '',
                                                                 deco_text.strip('. \n'),
                                                                 ' (' + source.upper().replace('_', ' ') + ')'
                                                                 if source else '',
                                                                 end_symbol))
    return render_template('handschrift.html',
                           title=current_app.manuscript_dict[manuscript],
                           m_d=metadata,
                           bibl_ids=current_app.bibl_ids)


@bp.route('/bibliographie')
@login_required
def bibliography() -> dict:
        """ Bibliography route function

        :return: Template to use for Bibliography page
        :rtype: {str: str}
        """
        return render_template('bibliography.html')
