#!/usr/bin/env python
import unittest
from app import create_app, db
from app.models import User
from config import Config
from flask import template_rendered, message_flashed, current_app
from flask_login import current_user
from glob import glob
from lxml import etree


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    ELASTICSEARCH_URL = None
    WTF_CSRF_ENABLED = False
    XML_LOCATION = './test_xmls'


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


class TestRoutes(CoenoturTests):

    def test_file_load(self):
        """ Make sure all XML files can be loaded and pass Schema"""
        all_xmls = glob(Config.XML_LOCATION + '/*.xml')
        exceptions = []
        for x in all_xmls:
            try:
                etree.parse(x)
            except SyntaxError as E:
                exceptions.append(E)
        if exceptions != []:
            print('# Not All XML Files Passed\n| File | Error |\n| --- | --- |\n' + '\n'.join(['| {} | {} |'.format(x.filename.split('/')[-1], str(x).split('(')[0]) for x in exceptions]))
            self.fail()
        else:
            print('# All XML Files Passed')

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
            print('#All XML Files Passed')

    def test_project_member(self):
        with self.client as c:
            c.post('/auth/login', data=dict(username='project.member', password="some_password"),
                        follow_redirects=True)
            self.assertEqual(current_user.email, 'project.member@uni-hamburg.de',
                             'Correct User should have been logged in.')
            c.get('/', follow_redirects=True)
            self.assertIn('index.html', [x[0].name for x in self.templates])
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
            self.assertEqual(metadata['page_size'], '325 mm x 243 mm')
            self.assertEqual(metadata['dim_written'], '24,0 cm x 16,5 cm')
            self.assertIn('der Anfang der Capitula von Gregor von Tours fehlt; die\n                           Handschrift bricht im ersten Buch von Sulpicius Severus ab (MUNSON).',
                          metadata['condition'])
            self.assertEqual('2', metadata['num_columns'])
            self.assertEqual('33', metadata['written_lines'])
            self.assertEqual(metadata['script_desc'], ['Minuskel'])
            self.assertEqual(metadata['hand_desc'], ['mehrere Hände'])
            self.assertEqual(metadata['exlibris'], ['fol. 7 Exlibris von Antoine Faure'])
            self.assertEqual(metadata['online_description'], ['<a href="https://archivesetmanuscrits.bnf.fr/ark:/12148/cc60091v" target="_blank">https://archivesetmanuscrits.bnf.fr/ark:/12148/cc60091v</a>'])
            self.assertEqual(metadata['illuminations'], ['- fol. 24r 215r - Federzeichnungen (FIRST GREAT SOURCE!)',
                                                         '- fol. 1r-2r - Cool drawings (SECOND GREAT SOURCE).'])

            # Test Neumen & Marginal notes
            c.get('/handschrift/Tours_BM_10_desc.xml', follow_redirects=True)
            metadata = self.get_context_variable('m_d')
            self.assertEqual(metadata['neumen'], ['fol. 164r - Neumen im Stil von Fleury (MUNSON).'])
            self.assertEqual(metadata['marginal'], ['Die Kapitelübersicht weicht von der üblichen Weise\n'
                                                    '                                ab, die übliche Einteilung ist aber von '
                                                    'einer späteren Hand\n'
                                                    '                                hinzugefügt worden. (COLLON).'])
            self.assertEqual(metadata['online_description'], ['Another_strange_idno'])
            self.assertEqual(metadata['digital_representations'], ['Some_strange_id'])
            self.assertEqual(metadata['general_notes'],
                             ['Die Zuschreibung nach Tours erfolgt vor allem aufgrund des Exlibris vom 12. Jhd.; Überlegungen, die Entstehung der Handschrift in Leury zu verorten, verweisen auf die Neumierungen auf fol. 163r, die floriazensischen Ursprungs sind. Diese Neumen könnten durch eine Ausleihe nach Fleury oder durch einen St-Martin besuchenden floriazensischen Mönch angefertigt worden sein, ohne dass die Entstehung der gesamten Handschrift deshalb in Fleury gesucht werden muss (MOSTERT).'])


            # Test tironischen Noten & Provenence (notes)
            c.get('/handschrift/Berlin_SB_Ham_82_desc.xml', follow_redirects=True)
            metadata = self.get_context_variable('m_d')
            self.assertEqual(metadata['tironoten'], ['fol. 58v <em>hic</em> (MARTINELLUS.DE)'])
            self.assertEqual(metadata['provenance'], ['St-Bénigne in Dijon'])
            self.assertEqual(metadata['provenance_notes'],
                             ['Verse auf 435r aus dem 10. und 11. Jhd. weisen darauf hin, dass die Handschrift bereits im 10. Jhd. unter Wilhelm von Volpiano in St-Bénigne war. Dort blieb sie bis mindestens ins 17. Jahrhundert, wie eine Abschrift des Bibliothekskatalog zwischen 1592 und 1682 bestätigt (FINGERNAGEL).'])
            self.assertEqual(metadata['binding'], ['Brauner Ledereinband über Pappe mit Streicheisengliederung, 19. Jhd.'])

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
