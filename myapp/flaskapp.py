import os
from flask import Flask, render_template, url_for, flash, redirect, request, send_from_directory, abort, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user

from forms import RegistrationForm, LoginForm
from flask_bcrypt import Bcrypt
from database import db
from models import User
from utils.claude_generate import generate_spec, MODEL as CLAUDE_MODEL
from utils.render_pptx import render, list_themes, GENERATED
from dotenv import load_dotenv

load_dotenv()  # This loads the .env file

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
bcrypt = Bcrypt(app)
db.init_app(app)


# Configure Flask-Login
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message = "로그인이 필요한 화면입니다."
login_manager.login_message_category = "info"
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route("/")
@app.route("/home")
def home():
    return render_template('home.html', user=current_user)


@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', title='내 정보')


@app.route("/register", methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        login_user(user, remember=True)
        flash('가입했습니다. 이제 덱을 만들어 보세요.', 'success')
        return redirect(url_for('generate'))
    return render_template('register.html', title='회원가입', form=form, user=current_user)


@app.route("/login", methods=['GET', 'POST'])
def login():
    # if the user is already authenticated, redirect them to home page
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            return redirect(url_for('home'))
        else:
            flash('이메일 또는 비밀번호가 맞지 않습니다.', 'danger')
    return render_template('login.html', title='로그인', form=form, user=current_user)



@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/generator', methods=['GET', 'POST'])
def generate():
    """GET: 입력 화면. POST(fetch): 명세 생성 → 렌더 → {file, json, slides} JSON."""
    if request.method == 'POST':
        try:
            number_of_slide = max(3, min(int(request.form.get('number_of_slide') or 8), 30))
        except ValueError:
            number_of_slide = 8
        user_text = (request.form.get('user_text') or '').strip()
        theme = request.form.get('template_choice') or 'climath'
        presentation_title = (request.form.get('presentation_title') or '').strip() or '발표 자료'
        presenter_name = (request.form.get('presenter_name') or '').strip()
        language = (request.form.get('language') or '한국어').strip()
        date = (request.form.get('date') or '').strip()
        if not user_text:
            return jsonify({'ok': False, 'error': '내용을 적어 주세요.'}), 400
        if theme not in {t['id'] for t in list_themes()}:
            return jsonify({'ok': False, 'error': f'모르는 테마: {theme}'}), 400
        try:
            spec = generate_spec(user_text, number_of_slide, presentation_title, presenter_name, language)
            result = render(spec, theme, date)
        except Exception as e:  # 모델 거절·렌더러 실패를 화면에 그대로 보여 준다
            app.logger.exception('generate failed')
            return jsonify({'ok': False, 'error': str(e)}), 500
        return jsonify({'ok': True, 'download': url_for('download_file', filename=result['file']),
                        'spec': url_for('download_file', filename=result['json']), 'slides': result['slides']})

    return render_template('generator.html', title='덱 만들기', themes=list_themes(), model=CLAUDE_MODEL)


@app.route('/render', methods=['POST'])
def render_only():
    """명세 JSON 을 직접 보내 렌더만 한다 (모델 호출 없음). body: {"spec": {...}, "theme": "climath"}"""
    body = request.get_json(silent=True) or {}
    spec = body.get('spec')
    if not isinstance(spec, dict) or not spec.get('slides'):
        return jsonify({'ok': False, 'error': 'spec.slides 가 필요합니다.'}), 400
    theme = body.get('theme') or spec.get('theme') or 'climath'
    try:
        result = render(spec, theme, body.get('date', ''))
    except Exception as e:
        app.logger.exception('render failed')
        return jsonify({'ok': False, 'error': str(e)}), 500
    return jsonify({'ok': True, 'download': url_for('download_file', filename=result['file']), 'slides': result['slides']})


@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    try:
        return send_from_directory(str(GENERATED), filename, as_attachment=True)

    except FileNotFoundError:
        abort(404)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(port=5001, debug=True)
