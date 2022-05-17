from flask import request
from flask_wtf import FlaskForm
from flask_babel import lazy_gettext as _l
from wtforms import StringField, BooleanField, SelectMultipleField, SubmitField
from wtforms.validators import DataRequired


class SearchForm(FlaskForm):
    simple_q = StringField(_l('Suche'), validators=[DataRequired()])

    def __init__(self, *args, **kwargs):
        if 'formdata' not in kwargs:
            kwargs['formdata'] = request.args
        if 'csrf_enabled' not in kwargs:
            kwargs['csrf_enabled'] = False
        super(SearchForm, self).__init__(*args, **kwargs)


class AdvancedSearchForm(SearchForm):
    simple_q = StringField(_l('Suche'))  # query string is not DataRequired here since someone might want to search on other criteria
    identifier = StringField(_l('Bezeichnung/Signatur'))
    orig_place = StringField(_l('Entstehungsort'))
    orig_place_cert = SelectMultipleField(_l('Sicherheit'),  choices=[('', ''),
                                                                      ('high', _l('Hoch')),
                                                                      ('medium', _l('Mittel')),
                                                                      ('low', _l('Niedrig'))])
    orig_year_start = StringField(_l('Jahr'))
    orig_year_end = StringField(_l('Jahr'))
    ms_item = StringField(_l('Inhalt'))
    person = StringField(_l('Personen'))
    person_role = SelectMultipleField(_l('Role'),  choices=[('', ''), ('Abt', _l('Abt')),
                                                                      ('Schreiber', _l('Schreiber'))])
    provenance = StringField(_l('Provenienz'))
    with_digitalisat = BooleanField(_l('Nur Handschriften mit Digitalisate'))
    with_scribe = BooleanField(_l('Nur Handschriften mit genannten Schreibern'))
    with_illuminations = BooleanField(_l('Nur illuminierte Handschriften'))
    with_exlibris = BooleanField(_l('Nur Handschriften mit "exlibris" Notierung'))
    with_tironoten = BooleanField(_l('Nur Handschriften mit tironischen Noten'))
    with_neumierung = BooleanField(_l('Nur neumierte Handschriften'))
    with_ink_analysis = BooleanField(_l('Nur Handschriften mit Tintenanalyse'))
    submit = SubmitField(_l('Suche Durchführen'), id="advancedSearchSubmit")
