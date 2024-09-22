from flask import Flask, render_template, request, flash, redirect, url_for
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
import os

app = Flask(__name__)

# 配置数据库连接
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://flaskuser:password@localhost/flaskappdb'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 设置一个安全的 secret_key
app.config['SECRET_KEY'] = os.urandom(24)

db = SQLAlchemy(app)
migrate = Migrate(app, db)

@app.route('/home')
def home():
    return render_template('home.html')

@app.route('/manage')
def manage():
    labs = Lab.query.all()  # 获取数据库中的所有实验室信息
    return render_template('manage.html', labs=labs)

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

@app.before_first_request
def create_tables():
    db.create_all()

class Lab(db.Model):
    __tablename__ = 'labs'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    location = db.Column(db.String(120), nullable=True)
    department = db.Column(db.String(120), nullable=True)

if __name__ == '__main__':
    app.run(debug=True)