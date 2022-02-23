from flask import request
from flask_wtf import FlaskForm
from flask_babel import lazy_gettext as _l
from flask_babel import _
from wtforms import StringField, BooleanField, SelectMultipleField, SelectField, SubmitField, HiddenField
from wtforms.validators import DataRequired, ValidationError, NumberRange
from wtforms.fields.html5 import IntegerField
from wtforms.widgets import CheckboxInput
from collections import OrderedDict
from random import randint


def validate_optional_number_range(minimum: int = -1, maximum: int = -1, message: str = None):
    """ Allows the validation of integer fields with a required number range but that are also optional
        I could not get WTForms to invalidate an integer field where the value was not within the range if it had the
        Optional() validator. I think this must have seen this as an empty field and thus erased all previous validation
        results since it correctly invalidates invalid data when the Optional() validator is not included.
    """

    def _length(form, field):
        if field.data:
            if int(field.data) < minimum or maximum != -1 and int(field.data) > maximum:
                raise ValidationError(message or "Field value must between between %i and %i." % (minimum, maximum))

    return _length


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
