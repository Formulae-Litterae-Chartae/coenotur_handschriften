import os
from dotenv import load_dotenv
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))


class Config(object):
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    POSTS_PER_PAGE = 10
    ELASTICSEARCH_URL = os.environ.get('ELASTICSEARCH_URL', 'http://localhost:9200')
    ES_CLIENT_CERT = os.environ.get('ES_CLIENT_CERT', '')
    ES_CLIENT_KEY = os.environ.get('ES_CLIENT_KEY', '')
    LANGUAGES = ['en', 'de', 'fr']
    BABEL_DEFAULT_LOCALE = 'de'
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 25)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') is not None
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    ADMINS = os.environ.get('ADMINS').split(';') if os.environ.get('ADMINS') else ['no-reply@example.com']
    SESSION_TYPE = 'filesystem'
    # This should only be changed to True when collecting search queries and responses for mocking ES
    SAVE_REQUESTS = False
    PDF_ENCRYPTION_PW = os.environ.get('PDF_ENCRYPTION_PW', 'hard_pw')
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', True)
    REMEMBER_COOKIE_SECURE = os.environ.get('REMEMBER_COOKIE_SECURE', True)
    REDIS_URL = os.environ.get('REDIS_URL') or 'redis://'
