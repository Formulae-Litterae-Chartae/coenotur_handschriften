from flask import render_template, current_app
from flask_babel import _
from app.email import send_email
from app.models import User


def send_password_reset_email(user: User):
    token = user.get_reset_password_token()
    send_email(_('[Coenotur Projekt] Passwort zurücksetzen'),
               sender=current_app.config['ADMINS'][0],
               recipients=[user.email],
               text_body=render_template('auth/email_reset_password.txt', user=user, token=token),
               html_body=render_template('auth/email_reset_password.html', user=user, token=token))


def send_email_reset_email(user: User, new_email: str):
    token = user.get_reset_email_token(new_email)
    send_email(_('[Coenotur Projekt] Emailadresse ändern'),
               sender=current_app.config['ADMINS'][0],
               recipients=[new_email],
               text_body=render_template('auth/email_reset_email.txt', user=user, token=token),
               html_body=render_template('auth/email_reset_email.html', user=user, token=token))
