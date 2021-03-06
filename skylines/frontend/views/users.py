from email.mime.text import MIMEText
from email.utils import formatdate
import smtplib

from flask import Blueprint, request, render_template, redirect, url_for, abort, current_app, flash, g, jsonify
from flask.ext.babel import _
from werkzeug.exceptions import ServiceUnavailable

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from skylines.database import db
from skylines.model import User
from skylines.model.event import create_new_user_event
from skylines.lib.vary import vary
from skylines.schemas import UserSchema, CurrentUserSchema, ValidationError

users_blueprint = Blueprint('users', 'skylines')


@users_blueprint.route('/')
@vary('accept')
def index():
    if 'application/json' not in request.headers.get('Accept', ''):
        return render_template('ember-page.jinja', active_page='settings')

    users = User.query() \
        .options(joinedload(User.club)) \
        .order_by(func.lower(User.name))

    fields = ['id', 'name']

    if 'club' in request.args:
        users = users.filter_by(club_id=request.args.get('club'))
    else:
        fields.append('club')

    return jsonify(users=UserSchema(only=fields).dump(users, many=True).data)


@users_blueprint.route('/new')
def new():
    return render_template('ember-page.jinja', active_page='settings')


@users_blueprint.route('/new', methods=['POST'])
def new_post():
    json = request.get_json()
    if json is None:
        return jsonify(error='invalid-request'), 400

    try:
        data = CurrentUserSchema(only=('email', 'firstName', 'lastName', 'password')).load(json).data
    except ValidationError, e:
        return jsonify(error='validation-failed', fields=e.messages), 422

    user = User(**data)

    user.created_ip = request.remote_addr
    db.session.add(user)

    create_new_user_event(user)

    db.session.commit()

    flash(_('Welcome to SkyLines, %(user)s! You can now log in and share your flights with the world!', user=user))

    return jsonify(user=UserSchema().dump(user).data)


@users_blueprint.route('/recover')
def recover():
    return render_template('ember-page.jinja', active_page='settings')


@users_blueprint.route('/recover', methods=['POST'])
def recover_post():
    json = request.get_json()
    if json is None:
        return jsonify(error='invalid-request'), 400

    if 'recoveryKey' in json:
        return recover_step2_post(json)
    else:
        return recover_step1_post(json)


def recover_step1_post(json):
    try:
        data = CurrentUserSchema(only=('email',)).load(json).data
    except ValidationError, e:
        return jsonify(error='validation-failed', fields=e.messages), 422

    user = User.by_email_address(data['email_address'])
    if not user:
        return jsonify(error='email-unknown'), 422

    user.generate_recover_key(request.remote_addr)
    try:
        send_recover_mail(user)
    except ServiceUnavailable:
        return jsonify(error='mail-service-unavailable'), 503

    db.session.commit()

    return jsonify()


def send_recover_mail(user):
    text = u"""Hi %s,

you have asked to recover your password (from IP %s).  To enter a new
password, click on the following link:

 http://skylines.aero/users/recover?key=%x

The SkyLines Team
""" % (unicode(user), request.remote_addr, user.recover_key)

    msg = MIMEText(text.encode('utf-8'), 'plain', 'utf-8')
    msg['Subject'] = 'SkyLines password recovery'
    msg['From'] = current_app.config['EMAIL_FROM']
    msg['To'] = user.email_address.encode('ascii')
    msg['Date'] = formatdate(localtime=1)

    try:
        smtp = smtplib.SMTP(current_app.config['SMTP_SERVER'])
        smtp.ehlo()
        smtp.sendmail(current_app.config['EMAIL_FROM'].encode('ascii'),
                      user.email_address.encode('ascii'), msg.as_string())
        smtp.quit()

    except:
        print text
        raise ServiceUnavailable(description=_(
            "The mail server is currently not reachable. "
            "Please try again later or contact the developers."))


def recover_step2_post(json):
    try:
        data = CurrentUserSchema(only=('password', 'recoveryKey')).load(json).data
    except ValidationError, e:
        return jsonify(error='validation-failed', fields=e.messages), 422

    user = User.by_recover_key(int(data['recover_key'], base=16))
    if not user:
        return jsonify(error='recovery-key-unknown'), 422

    user.password = data['password']
    user.recover_key = None

    db.session.commit()

    return jsonify()


@users_blueprint.route('/check-email', methods=['POST'])
def check_email():
    json = request.get_json()
    if not json:
        return jsonify(error='invalid-request'), 400

    email = json.get('email', '')

    result = 'available'
    if g.current_user and email == g.current_user.email_address:
        result = 'self'
    elif User.exists(email_address=email):
        result = 'unavailable'

    return jsonify(result=result)


@users_blueprint.route('/generate_keys')
def generate_keys():
    """Hidden method that generates missing tracking keys."""

    if not g.current_user or not g.current_user.is_manager():
        abort(403)

    for user in User.query():
        if user.tracking_key is None:
            user.generate_tracking_key()

    db.session.commit()

    return redirect(url_for('.index'))
