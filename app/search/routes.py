from flask import redirect, request, url_for, g, flash, current_app, render_template
from flask_babel import _
from .Search import advanced_query_index
from .forms import AdvancedSearchForm
from app.search import bp
from json import dumps


HIGHLIGHT_MAPPING = {'identifier.id': _('Signatur'),
                     'ms_item': _('Inhalt'),
                     'provenance': _('Geschichte der Handschrift'),
                     'person.name': _('Name'),
                     'orig_place.place': _('Ort'),
                     'orig_place.source': _('Quelle'),
                     'person.role': _('Role'),
                     'person.identifier': _('ID'),
                     'orig_place.cert': _('Sicherheit'),
                     'person': _('Person'),
                     'orig_place': _('Entstehungsort'),
                     'with_digitalisat': _('Digitalisate')
                     }


@bp.route("/simple", methods=["GET"])
def r_simple_search() -> redirect:
    if not g.search_form.validate():
        for k, m in g.search_form.errors.items():
            if k == 'simple_q':
                flash(m[0] + _(' Die einfache Suche funktioniert nur mit einem Suchwort.'))
        return redirect(url_for('.r_results', source='simple', simple_q=g.search_form.data['simple_q']))
    data = g.search_form.data
    return redirect(url_for('.r_results', source='simple', sort="_id", **data))


@bp.route("/results", methods=["GET"])
def r_results():
    source = request.args.get('source', None)
    # This means that someone simply navigated to the /results page without any search parameters
    if not source:
        return redirect(url_for('main.index'))
    posts_per_page = 10000
    page = 1
    search_args = dict(simple_q=request.args.get('simple_q'),
                       identifier=request.args.get('identifier'),
                       orig_place=request.args.get('orig_place'),
                       orig_place_cert=request.args.get('orig_place_cert', '').split('+'),
                       orig_year_start=request.args.get('orig_year_start'),
                       orig_year_end=request.args.get('orig_year_end'),
                       ms_item=request.args.get('ms_item'),
                       person=request.args.get('person'),
                       person_role=request.args.get('person_role', '').split('+'),
                       person_identifier=request.args.get('person_identifier'),
                       provenance=request.args.get('provenance'),
                       with_digitalisat=request.args.get('with_digitalisat'),
                       with_scribe=request.args.get('with_scribe'),
                       with_illuminations=request.args.get('with_illuminations'),
                       with_exlibris=request.args.get('with_exlibris'),
                       with_tironoten=request.args.get('with_tironoten'),
                       with_neumierung=request.args.get('with_neumierung'),
                       with_ink_analysis=request.args.get('with_ink_analysis'),
                       sort=request.args.get('sort', '_id'))
    posts, total, aggs = advanced_query_index(**search_args)
    return render_template('search/search.html', title=_('Suche'), posts=posts, current_page=page,
                           total_results=total, aggs=aggs, highlight_mapping=HIGHLIGHT_MAPPING)


@bp.route("/advanced_search", methods=["GET"])
def r_advanced_search():
    form = AdvancedSearchForm()
    data_present = [x for x in form.data if form.data[x]]
    if form.validate() and data_present and 'submit' in data_present:
        data = form.data
        for k, v in data.items():
            if isinstance(v, list):
                data[k] = '+'.join(v)
        return redirect(url_for('.r_results', source="advanced", **data))
    for k, m in form.errors.items():
        flash(k + ': ' + m[0])
    return render_template('search/advanced_search.html', form=form)


@bp.route("/doc", methods=["GET"])
def r_search_docs():
    """ Route to the documentation page for the advanced search"""
    return current_app.config['nemo_app'].render(template="search::documentation.html", url=dict())
