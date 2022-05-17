import logging
from logging.handlers import SMTPHandler, RotatingFileHandler
import os
from flask import Flask, request, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from flask_bootstrap import Bootstrap
from flask_babel import Babel, lazy_gettext as _l
from config import Config
from elasticsearch import Elasticsearch
from glob import glob
from lxml import etree
import re

db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
login.login_view = 'auth.login'
login.login_message = _l('Bitte loggen Sie sich ein, um Zugang zu erhalten.')
mail = Mail()
bootstrap = Bootstrap()
babel = Babel()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    if app.config['ELASTICSEARCH_URL']:
        if app.config['ES_CLIENT_CERT'] or app.config['ES_CLIENT_KEY']:
            app.elasticsearch = Elasticsearch(app.config['ELASTICSEARCH_URL'],
                                              use_ssl=True,
                                              verify_certs=True,
                                              client_cert=app.config['ES_CLIENT_CERT'],
                                              client_key=app.config['ES_CLIENT_KEY'])
        else:
            app.elasticsearch = Elasticsearch(app.config['ELASTICSEARCH_URL'])
    else:
        app.elasticsearch = None

    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    mail.init_app(app)
    bootstrap.init_app(app)
    babel.init_app(app)

    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.search import bp as search_bp
    app.register_blueprint(search_bp, url_prefix="/search")

    app.namespaces = {'tei': 'http://www.tei-c.org/ns/1.0'}
    xmls = glob(os.path.join(app.config['XML_LOCATION'], '*.xml'))


    def sort_manuscript_list(l: tuple) -> tuple:
        """ Sorts the dictionary of manuscript names in a more sensible manner

        :param d: dictionary of MS names
        :return: sorted dictionary of MS names
        """
        man_num = re.search(r'(.*?)(\d+)(.*)_desc', l[0])
        if man_num:
            return (man_num.group(1).lower(), int(man_num.group(2)) if man_num.group(2) else 0, man_num.group(3))
        return (l[0].lower(), 0, '')

    app.manuscript_list = list()
    app.manuscript_dict = dict()
    for x in xmls:
        xml = etree.parse(x)
        for t in xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:titleStmt/tei:title/text()', namespaces=app.namespaces):
            app.manuscript_list.append((os.path.basename(x), t))
            app.manuscript_dict[os.path.basename(x)] = t
    app.manuscript_list = sorted(app.manuscript_list, key=sort_manuscript_list)

    app.bibl_ids = dict()
    with app.open_resource('templates/bibliography.html', mode='r') as f:
        s = f.read()
    s = re.sub(r'\{%.*?%\}', '', s)
    h = etree.fromstring(s)
    for p in h.xpath('//p[@class="biblEntry"]'):
        app.bibl_ids[p.get('id')] = ''.join([etree.tostring(x, encoding=str) for x in p.iterchildren()])

    #for i in re.finditer(r'<p class="biblEntry" id="(.*?)">', s):
    #    app.bibl_ids.append(i.group(1))

    if not app.debug and not app.testing:
        if app.config['MAIL_SERVER']:
            auth = None
            if app.config['MAIL_USERNAME'] or app.config['MAIL_PASSWORD']:
                auth = (app.config['MAIL_USERNAME'],
                        app.config['MAIL_PASSWORD'])
            secure = None
            if app.config['MAIL_USE_TLS']:
                secure = ()
            mail_handler = SMTPHandler(
                mailhost=(app.config['MAIL_SERVER'], app.config['MAIL_PORT']),
                fromaddr='no-reply@' + app.config['MAIL_SERVER'],
                toaddrs=app.config['ADMINS'], subject='Microblog Failure',
                credentials=auth, secure=secure)
            mail_handler.setLevel(logging.ERROR)
            app.logger.addHandler(mail_handler)

        os.makedirs('logs', exist_ok=True)
        file_handler = RotatingFileHandler('logs/microblog.log',
                                           maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s '
            '[in %(pathname)s:%(lineno)d]'))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)

        app.logger.setLevel(logging.INFO)
        app.logger.info('Coenotur startup')

    return app


@babel.localeselector
def get_locale():
    return request.accept_languages.best_match(current_app.config['LANGUAGES'])

from app import models
