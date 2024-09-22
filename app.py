from flask import Flask, render_template, request, flash, redirect, url_for
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

@app.route('/home')
def home():
    return render_template('home.html')

@app.route('/manage', methods=['GET', 'POST'])
def manage():
    error = None
    if request.method == 'POST':
        lab_name = request.form['lab_name']
        new_lab = Lab(name=lab_name)
        try:
            db.session.add(new_lab)
            db.session.commit()
            flash(f'实验室名称已提交: {lab_name}', 'info')
            return redirect(url_for('manage'))
        except IntegrityError:
            db.session.rollback()
            error = '实验室名称已存在。'
            flash(error, 'danger')
    return render_template('manage.html', error=error)

@app.before_first_request
def create_tables():
    db.create_all()

class Lab(db.Model):
    __tablename__ = 'labs'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)

if __name__ == '__main__':
    app.run(debug=True)