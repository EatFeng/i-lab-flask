from flask import Flask, render_template, request, flash, redirect, url_for
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
import os
from paddlespeech.cli.tts.infer import TTSExecutor

app = Flask(__name__)

# 配置数据库连接
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://flaskuser:password@localhost/flaskappdb'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 设置一个安全的 secret_key
app.config['SECRET_KEY'] = os.urandom(24)

db = SQLAlchemy(app)
migrate = Migrate(app, db)

tts_executor = TTSExecutor()

@app.route('/home')
def home():
    return render_template('home.html')

@app.route('/manage')
def manage():
    labs = Lab.query.all()  # 获取数据库中的所有实验室信息
    return render_template('manage.html', labs=labs)

@app.route('/lab/<int:lab_id>', methods=['GET', 'POST'])
def lab(lab_id):
    lab = Lab.query.get_or_404(lab_id)
    if request.method == 'POST':
        if 'update_lab' in request.form:
            lab.name = request.form['lab_name']
            lab.location = request.form['lab_location']
            lab.department = request.form['lab_department']
            try:
                db.session.commit()
                flash('实验室信息已更新', 'info')
            except IntegrityError:
                db.session.rollback()
                flash('实验室名称已存在。', 'danger')
        elif 'add_guidance' in request.form:
            new_guidance = Guidance(
                lab_id=lab.id,
                point_id=request.form['point_id'],
                content=request.form['content'],
                audio_path=request.form['audio_path']
            )
            db.session.add(new_guidance)
            db.session.commit()
            flash('讲解内容已添加', 'info')
        elif 'update_guidance' in request.form:
            guidance_id = request.form['guidance_id']
            guidance = Guidance.query.get(guidance_id)
            if guidance:
                guidance.point_id = request.form['point_id']
                guidance.content = request.form['content']
                guidance.audio_path = request.form['audio_path']
                try:
                    db.session.commit()
                    flash('讲解内容已更新', 'info')
                except IntegrityError:
                    db.session.rollback()
                    flash('更新失败，请重试。', 'danger')
    guidances = Guidance.query.filter_by(lab_id=lab_id).all()
    return render_template('lab.html', lab=lab, guidances=guidances)

@app.route('/new-lab', methods=['GET', 'POST'])
def new_lab():
    if request.method == 'POST':
        lab_name = request.form['lab_name']
        lab_location = request.form['lab_location']
        lab_department = request.form['lab_department']
        new_lab = Lab(name=lab_name, location=lab_location, department=lab_department)
        try:
            db.session.add(new_lab)
            db.session.commit()
            flash('实验室信息已提交', 'info')
            return redirect(url_for('manage'))
        except IntegrityError:
            db.session.rollback()
            flash('实验室名称已存在。', 'danger')
    return render_template('new_lab.html')

@app.route('/lab/<int:lab_id>/generate-audio/<int:guidance_id>', methods=['POST'])
def generate_audio(lab_id, guidance_id):
    guidance = Guidance.query.get(guidance_id)
    if guidance:
        # 生成音频
        audio_file_path = f'./output/{guidance_id}.wav'
        tts_executor(text=guidance.content, output='./static' + audio_file_path)
        # 更新数据库
        guidance.audio_path = audio_file_path
        db.session.commit()
        flash('音频生成成功', 'info')
    else:
        flash('找不到记录', 'danger')
    return redirect(url_for('lab', lab_id=lab_id))

@app.before_first_request
def create_tables():
    db.create_all()

class Lab(db.Model):
    __tablename__ = 'labs'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    location = db.Column(db.String(120), nullable=True)
    department = db.Column(db.String(120), nullable=True)

class Guidance(db.Model):
    __tablename__ = 'guidance'
    id = db.Column(db.Integer, primary_key=True)
    lab_id = db.Column(db.Integer, db.ForeignKey('labs.id'), nullable=False)
    point_id = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=True)
    audio_path = db.Column(db.String(120), nullable=True)

if __name__ == '__main__':
    app.run(debug=True)