import os
from flask import Flask
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from paddlespeech.cli.tts.infer import TTSExecutor

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://192.168.4.80:8081/*",
                                 "methods": ["GET", "POST"]}})

# 配置数据库连接
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://flaskuser:password@localhost/flaskappdb'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 设置一个安全的 secret_key
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')

db = SQLAlchemy(app)
migrate = Migrate(app, db)

tts_executor = TTSExecutor()

from i_lab_flask import views, errors

@app.before_first_request
def create_tables():
    db.create_all()
