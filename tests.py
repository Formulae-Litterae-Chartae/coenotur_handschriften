#!/usr/bin/env python
import unittest
from unittest.mock import patch, mock_open
from app import create_app, db, mail
from app.models import User
from app.auth import forms as auth_forms
from app.search import forms as search_forms, routes as search_routes, Search
from config import Config
from flask import template_rendered, message_flashed, current_app, url_for
from flask_login import current_user
from flask_babel import _
from glob import glob
from lxml import etree
import pdfkit
import os
import sys
from logging.handlers import SMTPHandler
from wtforms.validators import ValidationError
from collections import OrderedDict
from elasticsearch import Elasticsearch
from fake_es import FakeElasticsearch
from copy import copy
import re


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    #ELASTICSEARCH_URL = None
    WTF_CSRF_ENABLED = False
    XML_LOCATION = './test_xmls'


class SSLESConfig(TestConfig):
    ELASTICSEARCH_URL = "https://some.secure.server/elasticsearch"
    ES_CLIENT_CERT = "SomeFile"
    ES_CLIENT_KEY = "SomeOtherFile"


class NormalESConfig(TestConfig):
    ELASTICSEARCH_URL = "Normal ES Server"


class AllFilesConfig(TestConfig):
    XML_LOCATION = './xmls'


class InitConfig(Config):
    TESTING = False
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    ELASTICSEARCH_URL = None
    WTF_CSRF_ENABLED = False
    XML_LOCATION = './test_xmls'
    MAIL_SERVER = 'localhost'
    MAIL_PORT = 8025
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'ADMIN'
    MAIL_PASSWORD = 'SomePassword'


class CoenoturTests(unittest.TestCase):

    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self._ctx = self.app.test_request_context()
        self._ctx.push()
        self.templates = []
        self.flashed_messages = []
        template_rendered.connect(self._add_template)
        message_flashed.connect(self._add_flash_message)
        db.create_all()
        u = User(username="project.member", email="project.member@uni-hamburg.de", project_team=True)
        u.set_password('some_password')
        db.session.add(u)
        u = User(username="not.project", email="not.project@uni-hamburg.de", project_team=False)
        u.set_password('some_other_password')
        db.session.add(u)
        db.session.commit()
        self.maxDiff = None

    def tearDown(self):
        template_rendered.disconnect(self._add_template)
        message_flashed.disconnect(self._add_flash_message)
        db.session.remove()
        db.drop_all()

    def _add_flash_message(self, app, message, category):
        self.flashed_messages.append((message, category))

    def _add_template(self, app, template, context):
        if len(self.templates) > 0:
            self.templates = []
        self.templates.append((template, context))

    def get_context_variable(self, name):
        """
        Returns a variable from the context passed to the
        template. Only works if your version of Flask
        has signals support (0.6+) and blinker is installed.
        Raises an AttributeError exception if 'name' does
        not exist in context.
        :param name: name of variable
        """

        for template, context in self.templates:
            if name in context:
                return context[name]
        raise AttributeError('{} does not exist in this context')


class TestXmlLoad(CoenoturTests):

    def setUp(self):
        self.app = create_app(AllFilesConfig)
        self.client = self.app.test_client()
        self._ctx = self.app.test_request_context()
        self._ctx.push()
        self.templates = []
        self.flashed_messages = []
        os.environ.update({'CI': 'True'})
        template_rendered.connect(self._add_template)
        message_flashed.connect(self._add_flash_message)
        db.create_all()
        u = User(username="project.member", email="project.member@uni-hamburg.de", project_team=True)
        u.set_password('some_password')
        db.session.add(u)
        db.session.add(u)
        db.session.commit()

    def test_file_load(self):
        """ Make sure all XML files can be loaded and pass Schema"""
        all_xmls = glob(self.app.config['XML_LOCATION'] + '/*.xml')
        os.makedirs('./pdfs', exist_ok=True)
        exceptions = []
        for x in all_xmls:
            try:
                etree.parse(x)
            except SyntaxError as E:
                exceptions.append(E)

        if exceptions != []:
            print('# Not All XML Files Passed\n| File | Error |\n| --- | --- |\n' + '\n'.join(['| {} | {} |'.format(x.filename.split('/')[-1], str(x).split('(')[0]) for x in exceptions]))
        else:
            print('# All XML Files Passed')

    def test_produce_new_pdfs(self):
        """ Produce new PDFs from the XML files that have changed from master"""
        if os.environ.get('CI'):
            all_xmls = glob(self.app.config['XML_LOCATION'] + '/*.xml')
            all_pdfs = glob('./app/static/pdfs/*.pdf')
            for pdf in all_pdfs:
                os.remove(pdf)
            sys.stdout.write('Old PDFs removed\n')
            sys.stdout.flush()
            for xml in all_xmls:
                xml_file = os.path.basename(xml.strip('"'))
                with self.client as c:
                    c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                           follow_redirects=True)
                    r = c.get('/handschrift/{}'.format(xml_file), follow_redirects=True)
                    html = etree.HTML(r.get_data(as_text=True))
                    span = etree.fromstring('<footer style="font-size:small;">https://coenotur.fruehmittelalterprojekte.uni-hamburg.de/handschrift/{}</footer>'.format(xml_file))
                    watermark = etree.fromstring('<div style="position:fixed;bottom:20%;left:5px;opacity:0.2;z-index:99;color:red;transform:rotate(-45deg);font-size:15em;">Coenotur Project</div>')
                    inner_div = html.xpath('//div[table]')[0]
                    if html.xpath('.//span[@id="pdfLink"]'):
                        pdf_link = html.xpath('.//span[@id="pdfLink"]')[0]
                        link_parent = pdf_link.getparent()
                        link_parent.remove(pdf_link)
                    for collapse in inner_div.xpath('.//div[@class="collapse"]'):
                        for collapse_key in collapse.keys():
                            collapse.set(collapse_key, '')
                    inner_div.append(span)
                    inner_div.append(watermark)
                    pdf_options = {'quiet': ''}
                    pdfkit.from_string(etree.tostring(html, encoding=str, pretty_print=True),
                                       './app/static/pdfs/{}'.format(xml_file.replace('.xml', '.pdf')),
                                       css='./app/static/css/styles.css', options=pdf_options)
                    sys.stdout.write('.')
                    sys.stdout.flush()


class TestInit(CoenoturTests):

    def setUp(self):
        self.app = create_app(InitConfig)
        self.client = self.app.test_client()
        self._ctx = self.app.test_request_context()
        self._ctx.push()

    def test_non_secure_es_server(self):
        """ Make sure that an ES server with no SSL security is correctly initiated"""
        app = create_app(NormalESConfig)
        self.assertEqual(app.elasticsearch.transport.hosts[0]['host'], NormalESConfig.ELASTICSEARCH_URL.lower())

    def test_secure_es_server(self):
        """ Make sure that an ES server with no SSL security is correctly initiated"""
        app = create_app(SSLESConfig)
        self.assertEqual(app.elasticsearch.transport.hosts[0]['host'],
                         'some.secure.server',
                         'Host server name should be correct.')
        self.assertTrue(app.elasticsearch.transport.hosts[0]['use_ssl'], 'SSL should be enabled.')

    def test_manuscript_sorting(self):
        """ Make sure that manuscripts are sorted correctly for the handschriften list"""
        self.assertEqual([('Berlin_SB_Ham_82_desc.xml', 'Berlin, SB, Hamilton 82'),
                          ('Paris_BnF_Latin_2204_desc.xml', 'Paris, BnF, Latin 2204'),
                          ('Paris_BnF_Latin_4418_desc.xml', 'Paris, BnF, Latin 4418'),
                          ('some_weird_manuscript_name.xml', 'Tours, BM, 1019'),
                          ('Tours_BM_10_desc.xml', 'Tours, BM, 10'),
                          ('Tours_BM_193_desc.xml', 'Tours, BM, 193')],
                         self.app.manuscript_list[:6])

    def test_mail_setup(self):
        """ Make sure email for error logging is set up correctly"""
        mail_logger = [x for x in self.app.logger.handlers if isinstance(x, SMTPHandler)][0]
        self.assertEqual(mail_logger.mailhost, 'localhost')
        self.assertEqual(mail_logger.username, 'ADMIN')
        self.assertEqual(mail_logger.password, 'SomePassword')
        self.assertEqual(mail_logger.secure, ())


class TestForms(CoenoturTests):

    def test_user_registration_form(self):
        """ Make sure a new user can register"""
        form = auth_forms.RegistrationForm(username='some_new_user',
                                           email='new_user@email.com',
                                           password='aGreatPassword',
                                           password2='aGreatPassword')
        self.assertTrue(form.validate(), 'New user should be able to register')
        form = auth_forms.RegistrationForm(username='some_new_user',
                                           email='new_user@email.com',
                                           password='aGreatPassword',
                                           password2='aBadPassword')
        self.assertFalse(form.validate(), 'Passwords that do not match should not validate')
        form = auth_forms.RegistrationForm(username='some_new_user',
                                           email='bad_email_address',
                                           password='aGreatPassword',
                                           password2='aGreatPassword')
        self.assertFalse(form.validate(), 'An invalid email address should not validate')
        form = auth_forms.RegistrationForm(username='some_new_user',
                                           email='new_user@email.com',
                                           password='aGreatPassword',
                                           password2='aGreatPassword',
                                           default_locale='it')
        self.assertFalse(form.validate(), 'An invalid default_locale should not validate')
        form = auth_forms.RegistrationForm(username='project.member',
                                           email='project.member@uni-hamburg.de',
                                           password='aGreatPassword',
                                           password2='aGreatPassword')
        with self.assertRaisesRegex(ValidationError, _('Bitte wählen Sie einen anderen Benutzername.')):
            form.validate_username(form.username)
        with self.assertRaisesRegex(ValidationError, _('Bitte wählen Sie eine andere Emailaddresse.')):
            form.validate_email(form.email)
        self.assertFalse(form.validate())


class TestRoutes(CoenoturTests):

    def test_file_load_with_fail(self):
        """ Make sure all XML files can be loaded and pass Schema"""
        all_xmls = glob(Config.XML_LOCATION + '/*.xml')
        exceptions = []
        for x in all_xmls:
            try:
                etree.parse(x)
            except SyntaxError as E:
                exceptions.append(E)
        if exceptions != []:
            print('# Not All XML Files Passed')
            print('| File | Error |\n| :--- | :--- |\n' + '\n'.join(['| {} | {} |'.format(x.filename.split('/')[-1], str(x).split('(')[0]) for x in exceptions]))
            self.fail()
        else:
            print('# All XML Files Passed')

    def test_project_member(self):
        with self.client as c:
            c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                        follow_redirects=True)
            self.assertEqual(current_user.email, 'project.member@uni-hamburg.de',
                             'Correct User should have been logged in.')
            c.get('/', follow_redirects=True)
            self.assertIn('index.html', [x[0].name for x in self.templates])
            c.get('/bibliographie', follow_redirects=True)
            self.assertIn('bibliography.html', [x[0].name for x in self.templates])
            c.get('/handschriften', follow_redirects=True)
            self.assertEqual(len(self.get_context_variable('handschriften_dict')), len(current_app.manuscript_list),
                             'All XML files should be shown in the Handschriftenliste')
            c.get('/handschrift/Paris_BnF_Latin_2204_desc.xml', follow_redirects=True)
            self.assertEqual(self.get_context_variable('title'), current_app.manuscript_dict['Paris_BnF_Latin_2204_desc.xml'])
            metadata = self.get_context_variable('m_d')
            self.assertIn('Faure 6', metadata['old_sigs'])
            self.assertIn('Hagiographie', [x['class'] for x in metadata['contents']])
            self.assertCountEqual(['Gregor von Tours', 'Venantius Fortunatus'], [x['author'] for x in metadata['contents']])
            self.assertCountEqual(['Libri octo miraculorum', 'Vita S. Martini, Liber Primus'], [x['title'] for x in metadata['contents']])
            self.assertEqual(['Latein', 'Latein'], [x['language'] for x in metadata['contents']])
            self.assertCountEqual(['10r-208v', '209r-215v'], [x['locus'] for x in metadata['contents']])
            sub_items = [x['parts'] for x in metadata['contents'] if x['title'] == 'Libri octo miraculorum'][0]
            self.assertCountEqual(['Liber in gloriam martyrum',
                                   'Liber Primus',
                                   'Passione et Virtutibus Sancti Iuliani Martyris',
                                   'De Virtutibus Sancti Martini',
                                   'Liber Secundus',
                                   'Liber Tertius',
                                   'Liber Quartus',
                                   'Liber Vitae Patrum',
                                   'Liber in gloria confessorum'],
                                  [x['title'] for x in sub_items])
            self.assertCountEqual(['10r',
                                   '10v-53v',
                                   '54r-69v',
                                   '69v-84r',
                                   '84r-100v',
                                   '100v-114r',
                                   '114r-123r',
                                   '123r-172r',
                                   '172r-208v'],
                                  [x['locus'] for x in sub_items])
            self.assertIn('Some special note', [x['notes'] for x in sub_items])
            self.assertNotIn('parts', [x for x in metadata['contents'] if x['title'] == 'Vita S. Martini, Liber Primus'][0])
            self.assertEqual(metadata['origin']['place'],
                             ['Westfrankreich <span class="cert-medium" title="Sicherheit: mittel">&#11044;</span> (BISCHOFF)'])
            self.assertEqual(metadata['origin']['date'],
                             ['9. Jhd., ca. 1./2. Viertel <span class="cert-medium" title="Sicherheit: mittel">&#11044;</span> (BISCHOFF)'])
            self.assertEqual(metadata['origin']['commentary'],
                             ['Wenig scheint gesichert. Die Handschrift sieht nicht besonders turonisch\n                        aus.'])
            self.assertEqual(metadata['obj_form'], 'codex')
            self.assertEqual(metadata['obj_material'], 'Pergament')
            self.assertEqual(metadata['num_pages'], '215')
            self.assertEqual(metadata['page_size'], ['325 mm x 243 mm'])
            self.assertEqual(metadata['dim_written'], ['24,0 cm x 16,5 cm'])
            self.assertIn('der Anfang der Capitula von Gregor von Tours fehlt; die\n                           Handschrift bricht im ersten Buch von Sulpicius Severus ab (MUNSON).',
                          metadata['condition'])
            self.assertEqual('2', metadata['num_columns'])
            self.assertEqual('33', metadata['written_lines'])
            self.assertEqual(metadata['script_desc'], ['Minuskel'])
            self.assertEqual(metadata['hand_desc'], ['mehrere Hände'])
            self.assertEqual(metadata['exlibris'], ['fol. 7 Exlibris von Antoine Faure'])
            self.assertEqual(metadata['online_description'], ['<a href="https://archivesetmanuscrits.bnf.fr/ark:/12148/cc60091v" target="_blank">https://archivesetmanuscrits.bnf.fr/ark:/12148/cc60091v</a>'])
            self.assertEqual(metadata['illuminations']['Allgemeine Miniaturen'], ['fol. 24r 215r - Federzeichnungen (FIRST GREAT SOURCE!)',
                                                         'fol. 1r-2r - Cool drawings (SECOND GREAT SOURCE).'])

            # Test Neumen & Marginal notes
            c.get('/handschrift/Tours_BM_10_desc.xml', follow_redirects=True)
            metadata = self.get_context_variable('m_d')
            self.assertEqual(metadata['neumen'], ['fol. 164r - Neumen im Stil von Fleury (MUNSON).'])
            self.assertEqual(metadata['marginal'], ['Die Kapitelübersicht weicht von der üblichen Weise\n'
                                                    '                                ab, die übliche Einteilung ist aber von '
                                                    'einer späteren Hand\n'
                                                    '                                hinzugefügt worden (COLLON).'])
            self.assertEqual(metadata['online_description'], ['Another_strange_idno'])
            self.assertEqual(metadata['digital_representations'], ['Some_strange_id'])
            self.assertEqual(metadata['general_notes'],
                             ['Die Zuschreibung nach Tours erfolgt vor allem aufgrund des Exlibris vom 12. Jhd.; Überlegungen, die Entstehung der Handschrift in Leury zu verorten, verweisen auf die Neumierungen auf fol. 163r, die floriazensischen Ursprungs sind. Diese Neumen könnten durch eine Ausleihe nach Fleury oder durch einen St-Martin besuchenden floriazensischen Mönch angefertigt worden sein, ohne dass die Entstehung der gesamten Handschrift deshalb in Fleury gesucht werden muss (MOSTERT).'])
            self.assertEqual(metadata['illuminations']['Ganzseite Miniaturen'],
                             ['fol. 24r 215r - Federzeichnungen (FIRST GREAT SOURCE!)'])
            self.assertEqual(metadata['illuminations']['Allgemeine Miniaturen'],
                             ['fol. 1r-2r - Cool drawings (SECOND GREAT SOURCE).'])


            # Test tironischen Noten & Provenence (notes)
            c.get('/handschrift/Berlin_SB_Ham_82_desc.xml', follow_redirects=True)
            metadata = self.get_context_variable('m_d')
            self.assertEqual(metadata['tironoten'], ['fol. 58v <em>hic</em> (MARTINELLUS.DE)'])
            self.assertEqual(metadata['provenance'], ['St-Bénigne in Dijon'])
            self.assertEqual(metadata['provenance_notes'],
                             ['Verse auf 435r aus dem 10. und 11. Jhd. weisen darauf hin, dass die Handschrift bereits im 10. Jhd. unter Wilhelm von Volpiano in St-Bénigne war. Dort blieb sie bis mindestens ins 17. Jahrhundert, wie eine Abschrift des Bibliothekskatalog zwischen 1592 und 1682 bestätigt (FINGERNAGEL).'])
            self.assertEqual(metadata['binding'], ['Brauner Ledereinband über Pappe mit Streicheisengliederung, 19. Jhd.'])
            self.assertIn({'<a href="{}" target="_blank">Vitriolische Eisengallustinten</a>'.format(url_for('static', filename='images/tinte/vitriolischeeisengallustinten.jpg')): 'fol. something'}, metadata['tintenanalyse']['ink']['Haupttext'])
            self.assertEqual(metadata['tintenanalyse']['pigments']['Rot']['<a href="{}" target="_blank">Zinnober</a>'.format(url_for('static', filename='images/tinte/zinnober.jpg'))]['Initiale'], 'fol. 4r, fol. 211v')

            # Test handDesc and scriptDesc <p>
            c.get('/handschrift/Tours_BM_1019_desc.xml', follow_redirects=True)
            metadata = self.get_context_variable('m_d')
            self.assertEqual(metadata['script_desc'], ['Some scriptDesc paragraph (MUNSON).'])
            self.assertEqual(metadata['hand_desc'], ['Some handDesc paragraph (MUNSON).'])
            self.assertEqual({'COLLON 1900': ['S. 736-739', '800'], 'DORANGE 1875': ['S. 447-448'], 'RAND 1929': []}, metadata['bibliography'])

            # Test noteStmt/note/p
            c.get('/handschrift/Tours_BM_193_desc.xml', follow_redirects=True)
            metadata = self.get_context_variable('m_d')
            self.assertEqual(metadata['general_notes'],
                             ['Dieses Missale wurde in St-Martin verwendet. Es findet sich weder im Katalog von Montfaucon, noch in dem von Chalmel, vermutlich, weil es so wertvoll war, dass es im Tresor und nicht in der Bibliothek gelagert wurde (DORANGE).'])

            # Test biblScope with @n but without @unit="pp"
            r = c.get('/handschrift/Paris_BnF_Latin_4418_desc.xml', follow_redirects=True)
            metadata = self.get_context_variable('m_d')
            self.assertEqual(metadata['bibliography']['UBL 2014'], ['passim'])
            c.get('/handschrift/Tours_BM_1019_desc_2.xml', follow_redirects=True)
            metadata = self.get_context_variable('m_d')
            self.assertEqual(metadata['pdf'], None)
            self.assertEqual(metadata['ink_notes'], '<a href="{idno}" target="_blank">{idno}</a>'.format(idno='https://coenotur.fruehmittelalterprojekte.uni-hamburg.de/tintenanalyse'))
            self.assertIn('fol. 89r-89v - Some text.', metadata['illuminations']['Allgemeine Miniaturen'])
            c.get('/handschrift/Tours_BM_1019_desc.xml', follow_redirects=True)
            metadata = self.get_context_variable('m_d')
            self.assertEqual(metadata['pdf'], url_for('static', filename='pdfs/Tours_BM_1019_desc.pdf'))

    def test_send_email_existing_user(self):
        """ Ensure that emails are constructed correctly"""
        with self.client as c:
            with mail.record_messages() as outbox:
                c.post('/auth/reset_password_request', data=dict(email="project.member@uni-hamburg.de"),
                       follow_redirects=True)
                self.assertEqual(len(outbox), 1, 'One email should be sent')
                self.assertEqual(outbox[0].recipients, ["project.member@uni-hamburg.de"],
                                 'The recipient email address should be correct.')
                self.assertEqual(outbox[0].subject, _('[Coenotur Projekt] Passwort zurücksetzen'),
                                 'The Email should have the correct subject.')
                self.assertIn(_('Sehr geehrte(r)') + ' project.member', outbox[0].html,
                              'The email text should be addressed to the correct user.')
                self.assertEqual(outbox[0].sender, 'no-reply@example.com',
                                 'The email should come from the correct sender.')
                self.assertIn(_('Die Anweisung zum Zurücksetzen Ihres Passworts wurde Ihnen per E-mail zugeschickt'), [x[0] for x in self.flashed_messages])
                c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                       follow_redirects=True)
                c.post('/auth/user', data={'email': 'new_email@email.com', 'email2': 'new_email@email.com'},
                       follow_redirects=True)
                self.assertEqual(len(outbox), 2, 'There should now be a second email in the outbox.')
                self.assertEqual(outbox[1].recipients, ["new_email@email.com"],
                                 'The recipient email address should be correct.')
                self.assertEqual(outbox[1].subject, _('[Coenotur Projekt] Emailadresse ändern'),
                                 'The Email should have the correct subject.')
                self.assertIn(_('Sehr geehrte(r)') + ' project.member', outbox[1].html,
                              'The email text should be addressed to the correct user.')
                self.assertEqual(outbox[1].sender, 'no-reply@example.com',
                                 'The email should come from the correct sender.')
                self.assertIn(_('Ein Link zur Bestätigung dieser Änderung wurde an Ihre neue Emailadresse zugeschickt'), [x[0] for x in self.flashed_messages])
                self.assertEqual(current_user.email, "project.member@uni-hamburg.de",
                                 "The email address should not be changed only by requesting the token.")

    def test_send_email_not_existing_user(self):
        """ Ensure that no email is sent to a non-registered email address"""
        with self.client as c:
            with mail.record_messages() as outbox:
                c.post('/auth/reset_password_request', data=dict(email="pirate.user@uni-hamburg.de"),
                       follow_redirects=True)
                self.assertEqual(len(outbox), 0, 'No email should be sent when the email is not in the database.')
                self.assertIn(_('Die Anweisung zum Zurücksetzen Ihres Passworts wurde Ihnen per E-mail zugeschickt'), [x[0] for x in self.flashed_messages])

    def test_reset_password_from_email_token(self):
        """ Make sure that a correct email token allows the user to reset their password while an incorrect one doesn't"""
        with self.client as c:
            user = User.query.filter_by(username='project.member').first()
            token = user.get_reset_password_token()
            # Make sure that the template renders correctly with correct token
            c.post(url_for('auth.reset_password', token=token, _external=True))
            self.assertIn('auth/reset_password.html', [x[0].name for x in self.templates])
            # Make sure the correct token allows the user to change their password
            c.post(url_for('auth.reset_password', token=token, _external=True),
                   data={'password': 'some_new_password', 'password2': 'some_new_password'})
            self.assertTrue(user.check_password('some_new_password'), 'User\'s password should be changed.')
            c.post(url_for('auth.reset_password', token='some_weird_token', _external=True),
                   data={'password': 'some_password', 'password2': 'some_password'}, follow_redirects=True)
            self.assertIn('auth/login.html', [x[0].name for x in self.templates])
            self.assertTrue(user.check_password('some_new_password'), 'User\'s password should not have changed.')
            # Make sure that a logged in user who comes to this page with a token is redirected to their user page with a flashed message
            c.post('/auth/login', data=dict(username='project.member', password="some_new_password"),
                   follow_redirects=True)
            c.post(url_for('auth.reset_password', token=token, _external=True), follow_redirects=True)
            self.assertIn('auth/login.html', [x[0].name for x in self.templates])
            self.assertIn(_('Sie sind schon eingeloggt. Sie können Ihr Password hier ändern.'), [x[0] for x in self.flashed_messages])
            self.assertEqual(repr(user), '<User project.member>')

    def test_reset_email_from_email_token(self):
        """ Make sure that a correct email token changes the user's email address while an incorrect one doesn't"""
        with self.client as c:
            c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                   follow_redirects=True)
            user = User.query.filter_by(username='project.member').first()
            token = user.get_reset_email_token('another_new_email@email.com')
            self.assertEqual(user.email, "project.member@uni-hamburg.de",
                             "The email address should not be changed only by requesting the token.")
            # Make sure that the template renders correctly with correct token
            c.post(url_for('auth.reset_email', token=token, _external=True))
            self.assertIn('auth/login.html', [x[0].name for x in self.templates])
            # Make sure the correct token allows the user to change their password
            self.assertEqual(user.email, 'another_new_email@email.com', 'User\'s email should be changed.')
            self.assertIn(_('Ihr Email wurde erfolgreich geändert. Sie lautet jetzt') + ' another_new_email@email.com.', [x[0] for x in self.flashed_messages])
            # Trying to use the same token twice should not work.
            c.post(url_for('auth.reset_email', token=token, _external=True))
            self.assertIn('auth/login.html', [x[0].name for x in self.templates])
            self.assertIn(_('Ihre Emailaddresse wurde nicht geändert. Versuchen Sie es erneut.'), [x[0] for x in self.flashed_messages])
            # Using an invalid token should not work.
            c.post(url_for('auth.reset_email', token='some_weird_token', _external=True), follow_redirects=True)
            self.assertIn(_('Der Token ist nicht gültig. Versuchen Sie es erneut.'), [x[0] for x in self.flashed_messages])
            self.assertIn('auth/login.html', [x[0].name for x in self.templates])
            self.assertEqual(user.email, 'another_new_email@email.com', 'User\'s email should not have changed.')

    def test_tintenanalyse(self):
        """ Make sure the HTML page for Tintenanalyse loads correctly"""
        with self.client as c:
            c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                   follow_redirects=True)
            c.get('/tintenanalyse', follow_redirects=True)
            self.assertIn('tintenanalyse.html', [x[0].name for x in self.templates])

    def test_logged_in_user(self):
        """ Test to make sure that a user who is already logged in is correctly redirected"""
        with self.client as c:
            c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                   follow_redirects=True)
            c.get('/auth/login', follow_redirects=True)
            self.assertIn('auth/login.html', [x[0].name for x in self.templates])

    def test_incorrect_login_info(self):
        """ Make sure that a user using incorrect login information is correctly redirected"""
        with self.client as c:
            c.post('/auth/login', data=dict(username='project.member', password="wrong_password"),
                   follow_redirects=True)
            self.assertIn(_('Benutzername oder Passwort ist ungültig'), [x[0] for x in self.flashed_messages])
            c.post('/auth/login', data=dict(username='nonexistent.member', password="some_password"),
                   follow_redirects=True)
            self.assertIn(_('Benutzername oder Passwort ist ungültig'), [x[0] for x in self.flashed_messages])

    def test_redirect_after_login(self):
        """ Make sure the user is redirected to their desired page after logging in"""
        with self.client as c:
            c.post('/auth/login?next=/handschriften', data=dict(username='project.member', password="some_password"),
                   follow_redirects=True)
            self.assertIn('handschriften.html', [x[0].name for x in self.templates])

    def test_user_logout(self):
        """ Make sure the logout function logs the user out"""
        with self.client as c:
            c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                   follow_redirects=True)
            self.assertTrue(current_user.is_authenticated, 'User should be logged in.')
            c.get('/auth/logout', follow_redirects=True)
            self.assertFalse(current_user.is_authenticated, 'User should now be logged out.')
            self.assertIn('auth/login.html', [x[0].name for x in self.templates])

    def test_user_change_prefs(self):
        """ Make sure that the user can change their language and password"""
        with self.client as c:
            c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                   follow_redirects=True)
            self.assertEqual(current_user.default_locale, 'de', '"de" should be the default language.')
            c.post('/auth/user/project.member', data={'new_locale': "en"})
            self.assertEqual(current_user.default_locale, 'en', 'User language should have been changed to "en"')
            c.post('/auth/user/project.member', data={'old_password': 'some_password', 'password': 'some_new_password',
                                                      'password2': 'some_new_password'},
                   follow_redirects=True)
            self.assertTrue(User.query.filter_by(username='project.member').first().check_password('some_new_password'),
                            'User should have a new password: "some_new_password".')
            self.assertIn('auth/login.html', [x[0].name for x in self.templates])
            self.assertIn(_("Sie haben Ihr Passwort erfolgreich geändert."), [x[0] for x in self.flashed_messages])

    def test_user_change_prefs_incorrect(self):
        """ Make sure that a user who gives the false old password is not able to change their password"""
        with self.client as c:
            c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                   follow_redirects=True)
            self.assertTrue(current_user.is_authenticated)
            c.post(url_for('auth.user', username='project.member'), data={'old_password': 'some_wrong_password',
                                                                            'password': 'some_new_password',
                                                                            'password2': 'some_new_password'},
                   follow_redirects=True)
            self.assertTrue(User.query.filter_by(username='project.member').first().check_password('some_password'),
                            'User\'s password should not have changed.')
            self.assertIn(_("Das ist nicht Ihr aktuelles Passwort."), [x[0] for x in self.flashed_messages])

    def test_reset_password_request(self):
        """ Make sure the reset_password_request page works correctly"""
        with self.client as c:
            c.get('/auth/reset_password_request', follow_redirects=True)
            self.assertIn('auth/reset_password_request.html', [x[0].name for x in self.templates])
            c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                   follow_redirects=True)
            c.get('/auth/reset_password_request', follow_redirects=True)
            self.assertIn('auth/login.html', [x[0].name for x in self.templates])
            self.assertIn(_('Sie sind schon eingeloggt. Sie können Ihr Password hier ändern.'), [x[0] for x in self.flashed_messages])

    @patch("app.search.routes.advanced_query_index")
    def test_search_results(self, mock_search):
        """ Make sure that the correct search results are passed to the search results form"""
        params = dict(simple_q='tours', sort='_id', source='simple')
        mock_search.return_value = [[], {"value": 0, "relation": "eq"}, {}]
        with self.client as c:
            c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                   follow_redirects=True)
            response = c.get('/search/simple?simple_q=tours')
            for p, v in params.items():
                self.assertRegex(str(response.location), r'{}={}'.format(p, v))
            c.get('/search/simple?simple_q=tours',
                  follow_redirects=True)
            mock_search.assert_called_with(simple_q='tours', identifier=None, orig_place=None, orig_place_cert=[''],
                                           orig_year_start=None, orig_year_end=None, ms_item=None, person=None,
                                           person_role=[''], person_identifier=None, provenance=None,
                                           with_digitalisat=None, with_scribe=None, with_illuminations=None,
                                           with_exlibris=None, with_tironoten=None, with_neumierung=None,
                                           with_ink_analysis=None, sort='_id')
            c.get('/search/simple?simple_q=')
            self.assertIn(_('Dieses Feld wird benötigt. Die einfache Suche funktioniert nur mit einem Suchwort.'),
                          [x[0] for x in self.flashed_messages])
            c.get('/search/results?simple_q=tours', follow_redirects=True)
            self.assertIn('index.html', [x[0].name for x in self.templates],
                          'Navigating to results page without "source" should redirect to index.html')
            c.get('/search/advanced_search?simple_q=&identifier=tours&orig_place=tours&orig_place_cert=&orig_year_start=&orig_year_end=&ms_item=&person=&person_role=&provenance=&with_digitalisat=&with_scribe=True&with_illuminations=&with_exlibris=True&with_tironoten=&with_neumierung=True&with_ink_analysis=&submit=True', follow_redirects=True)
            mock_search.assert_called_with(simple_q='', identifier='tours', orig_place='tours', orig_place_cert=[''],
                                           orig_year_start='', orig_year_end='', ms_item='', person='',
                                           person_role=[''], person_identifier=None, provenance='', with_digitalisat='False',
                                           with_scribe='True', with_illuminations='False', with_exlibris='True',
                                           with_tironoten='False', with_neumierung='True', with_ink_analysis='False',
                                           sort='_id')
            c.get('/search/advanced_search?simple_q=&identifier=tours&orig_place=tours&orig_place_cert=True&orig_year_start=&orig_year_end=&ms_item=&person=&person_role=&provenance=&with_digitalisat=&with_scribe=True&with_illuminations=&with_exlibris=True&with_tironoten=&with_neumierung=True&with_ink_analysis=&submit=True', follow_redirects=True)
            self.assertIn(_("orig_place_cert: 'True' ist kein gültige Auswahl für dieses Feld."),
                          [x[0] for x in self.flashed_messages])


class TestES(CoenoturTests):

    TEST_ARGS = {'test_simple_search': OrderedDict([('simple_q', 'tours'),
                                                    ('identifier', ''),
                                                    ('orig_place', ''),
                                                    ('orig_place_cert', ''),
                                                    ('orig_year_start', ''),
                                                    ('orig_year_end', ''),
                                                    ('ms_item', ''),
                                                    ('person', ''),
                                                    ('person_role', ''),
                                                    ('person_identifier', ''),
                                                    ('provenance', ''),
                                                    ('with_digitalisat', ''),
                                                    ('with_scribe', ''),
                                                    ('with_illuminations', ''),
                                                    ('with_exlibris', ''),
                                                    ('with_tironoten', ''),
                                                    ('with_neumierung', ''),
                                                    ('with_ink_analysis', ''),
                                                    ('sort', '_id')]),
                 'test_simple_search_wildcard': OrderedDict([('simple_q', 'evang*'),
                                                             ('identifier', ''),
                                                             ('orig_place', ''),
                                                             ('orig_place_cert', ''),
                                                             ('orig_year_start', ''),
                                                             ('orig_year_end', ''),
                                                             ('ms_item', ''),
                                                             ('person', ''),
                                                             ('person_role', ''),
                                                             ('person_identifier', ''),
                                                             ('provenance', ''),
                                                             ('with_digitalisat', ''),
                                                             ('with_scribe', ''),
                                                             ('with_illuminations', ''),
                                                             ('with_exlibris', ''),
                                                             ('with_tironoten', ''),
                                                             ('with_neumierung', ''),
                                                             ('with_ink_analysis', ''),
                                                             ('sort', '_id')]),
                 'test_with_bool_true': OrderedDict([('simple_q', 'evang*'),
                                                     ('identifier', ''),
                                                     ('orig_place', ''),
                                                     ('orig_place_cert', ''),
                                                     ('orig_year_start', ''),
                                                     ('orig_year_end', ''),
                                                     ('ms_item', ''),
                                                     ('person', ''),
                                                     ('person_role', ''),
                                                     ('person_identifier', ''),
                                                     ('provenance', ''),
                                                     ('with_digitalisat', 'True'),
                                                     ('with_scribe', 'True'),
                                                     ('with_illuminations', ''),
                                                     ('with_exlibris', 'True'),
                                                     ('with_tironoten', ''),
                                                     ('with_neumierung', ''),
                                                     ('with_ink_analysis', ''),
                                                     ('sort', '_id')]),
                 'test_flat_field_search': OrderedDict([('simple_q', ''),
                                                        ('identifier', ''),
                                                        ('orig_place', ''),
                                                        ('orig_place_cert', ''),
                                                        ('orig_year_start', ''),
                                                        ('orig_year_end', ''),
                                                        ('ms_item', 'evang*'),
                                                        ('person', ''),
                                                        ('person_role', ''),
                                                        ('person_identifier', ''),
                                                        ('provenance', 'tours'),
                                                        ('with_digitalisat', ''),
                                                        ('with_scribe', ''),
                                                        ('with_illuminations', ''),
                                                        ('with_exlibris', ''),
                                                        ('with_tironoten', ''),
                                                        ('with_neumierung', ''),
                                                        ('with_ink_analysis', ''),
                                                        ('sort', '_id')]),
                 'test_nested_field_search': OrderedDict([('simple_q', ''),
                                                        ('identifier', ''),
                                                        ('orig_place', 'tours'),
                                                        ('orig_place_cert', 'high'),
                                                        ('orig_year_start', ''),
                                                        ('orig_year_end', ''),
                                                        ('ms_item', ''),
                                                        ('person', 'adalbald*'),
                                                        ('person_role', ''),
                                                        ('person_identifier', 'scribe'),
                                                        ('provenance', ''),
                                                        ('with_digitalisat', ''),
                                                        ('with_scribe', ''),
                                                        ('with_illuminations', ''),
                                                        ('with_exlibris', ''),
                                                        ('with_tironoten', ''),
                                                        ('with_neumierung', ''),
                                                        ('with_ink_analysis', ''),
                                                        ('sort', '_id')]),
                 'test_year_search': OrderedDict([('simple_q', ''),
                                                  ('identifier', ''),
                                                  ('orig_place', ''),
                                                  ('orig_place_cert', ''),
                                                  ('orig_year_start', '400'),
                                                  ('orig_year_end', '450'),
                                                  ('ms_item', ''),
                                                  ('person', ''),
                                                  ('person_role', ''),
                                                  ('person_identifier', ''),
                                                  ('provenance', ''),
                                                  ('with_digitalisat', ''),
                                                  ('with_scribe', ''),
                                                  ('with_illuminations', ''),
                                                  ('with_exlibris', ''),
                                                  ('with_tironoten', ''),
                                                  ('with_neumierung', ''),
                                                  ('with_ink_analysis', ''),
                                                  ('sort', '_id')])
                 }

    def build_fake_es_filename(self, f_n: str = ''):
        """ Replace problematic characters in the fake_es filenames"""
        return re.sub(r'[\*\?\s]', '+', f_n)

    def test_build_sort_list(self):
        """ Ensure that build_sort_list returns the correct values"""
        self.assertEqual(Search.build_sort_list('_id'), '_id')
        self.assertEqual(Search.build_sort_list('date_asc'), [{'mid_date': {'order': 'asc'}}, '_id'])
        self.assertEqual(Search.build_sort_list('date_desc'), [{'mid_date': {'order': 'desc'}}, '_id'])

    def test_return_no_es(self):
        """ Ensure that when ElasticSearch is not active, calls to the search functions return empty results instead of errors"""
        self.app.elasticsearch = None
        test_args = copy(self.TEST_ARGS['test_simple_search'])
        hits, total, aggs = Search.advanced_query_index(**test_args)
        self.assertEqual(hits, [], 'Hits should be an empty list.')
        self.assertEqual(total, 0, 'Total should be 0')
        self.assertEqual(aggs, {}, 'Aggregations should be an empty dictionary.')

    @patch.object(Elasticsearch, "search")
    def test_lemma_simple_search(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_simple_search'])
        fake = FakeElasticsearch(self.build_fake_es_filename('&'.join(test_args.values())), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        self.search_aggs = fake.load_aggs()
        ids = fake.load_ids()
        test_args['orig_place_cert'] = test_args['orig_place_cert'].split('+')
        test_args['person_role'] = test_args['person_role'].split('+')
        mock_search.return_value = resp
        actual, _, _ = Search.advanced_query_index(**test_args)
        mock_search.assert_any_call(index='coenotur', doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['_id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_lemma_simple_search_wildcard(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_simple_search_wildcard'])
        fake = FakeElasticsearch(self.build_fake_es_filename('&'.join(test_args.values())), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        self.search_aggs = fake.load_aggs()
        ids = fake.load_ids()
        test_args['orig_place_cert'] = test_args['orig_place_cert'].split('+')
        test_args['person_role'] = test_args['person_role'].split('+')
        mock_search.return_value = resp
        actual, _, _ = Search.advanced_query_index(**test_args)
        mock_search.assert_any_call(index='coenotur', doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['_id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_with_bool_true(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_with_bool_true'])
        fake = FakeElasticsearch(self.build_fake_es_filename('&'.join(test_args.values())), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        self.search_aggs = fake.load_aggs()
        ids = fake.load_ids()
        test_args['orig_place_cert'] = test_args['orig_place_cert'].split('+')
        test_args['person_role'] = test_args['person_role'].split('+')
        mock_search.return_value = resp
        actual, _, _ = Search.advanced_query_index(**test_args)
        mock_search.assert_any_call(index='coenotur', doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['_id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_flat_field_search(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_flat_field_search'])
        fake = FakeElasticsearch(self.build_fake_es_filename('&'.join(test_args.values())), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        self.search_aggs = fake.load_aggs()
        ids = fake.load_ids()
        test_args['orig_place_cert'] = test_args['orig_place_cert'].split('+')
        test_args['person_role'] = test_args['person_role'].split('+')
        mock_search.return_value = resp
        actual, _, _ = Search.advanced_query_index(**test_args)
        mock_search.assert_any_call(index='coenotur', doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['_id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_nested_field_search(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_nested_field_search'])
        fake = FakeElasticsearch(self.build_fake_es_filename('&'.join(test_args.values())), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        self.search_aggs = fake.load_aggs()
        ids = fake.load_ids()
        test_args['orig_place_cert'] = test_args['orig_place_cert'].split('+')
        test_args['person_role'] = test_args['person_role'].split('+')
        mock_search.return_value = resp
        actual, _, _ = Search.advanced_query_index(**test_args)
        mock_search.assert_any_call(index='coenotur', doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['_id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_year_search(self, mock_search):
        test_args = copy(self.TEST_ARGS['test_year_search'])
        fake = FakeElasticsearch(self.build_fake_es_filename('&'.join(test_args.values())), 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        self.search_aggs = fake.load_aggs()
        ids = fake.load_ids()
        test_args['orig_place_cert'] = test_args['orig_place_cert'].split('+')
        test_args['person_role'] = test_args['person_role'].split('+')
        mock_search.return_value = resp
        actual, _, _ = Search.advanced_query_index(**test_args)
        mock_search.assert_any_call(index='coenotur', doc_type="", body=body)
        self.assertEqual(ids, [{"id": x['_id']} for x in actual])

    @patch.object(Elasticsearch, "search")
    def test_save_requests(self, mock_search):
        self.app.config['SAVE_REQUESTS'] = True
        test_args = copy(self.TEST_ARGS['test_year_search'])
        file_name_base = self.build_fake_es_filename('&'.join(test_args.values()))
        fake = FakeElasticsearch(file_name_base, 'advanced_search')
        body = fake.load_request()
        resp = fake.load_response()
        self.search_aggs = fake.load_aggs()
        ids = fake.load_ids()
        mock_search.return_value = resp
        test_args['orig_place_cert'] = test_args['orig_place_cert'].split('+')
        test_args['person_role'] = test_args['person_role'].split('+')
        with patch('builtins.open', new_callable=mock_open()) as m:
            with patch('json.dump') as mock_dump:
                actual, _, _ = Search.advanced_query_index(**test_args)
                mock_dump.assert_any_call(resp, m.return_value.__enter__.return_value, indent=2, ensure_ascii=False)
                mock_dump.assert_any_call(body, m.return_value.__enter__.return_value, indent=2, ensure_ascii=False)
                mock_dump.assert_any_call(ids, m.return_value.__enter__.return_value, indent=2, ensure_ascii=False)


def rebuild_search_mock_files(url_base="http://127.0.0.1:5000"):
    """Automatically rebuilds the mock files for the ElasticSearch tests.
    This requires that a local version of the app is running at url_base and that the config variable
    SAVE_REQUESTS is set to True.

    :param url_base: The base url at which the app is currently running.
    """
    import requests
    test_args = TestES.TEST_ARGS.items()
    for k, v in test_args:
        url_ext = []
        for x, y in v.items():
            url_ext.append('{}={}'.format(x, y))
        url = '{}/search/results?{}&source=advanced'.format(url_base, '&'.join(url_ext))
        r = requests.get(url)
        if r.status_code != 200:
            print(url + ' did not succeed. Status code: ' + str(r.status_code))
