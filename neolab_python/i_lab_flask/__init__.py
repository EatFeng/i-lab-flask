from transformers import AutoModelForCausalLM, AutoTokenizer
import os
from flask import Flask
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from paddlespeech.cli.tts.infer import TTSExecutor
from paddlespeech.cli.asr.infer import ASRExecutor
import torch

app = Flask(__name__)
CORS(app)

# 配置数据库连接
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://flaskuser:password@localhost/flaskappdb'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'F:/PythonProjects/neoLab/neolab_python/'
# 设置上传文件的最大尺寸为16MB
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
# 设置一个安全的 secret_key
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')

db = SQLAlchemy(app)
migrate = Migrate(app, db)

tts_executor = TTSExecutor()
asr_executor = ASRExecutor()

# 加载模型和分词器
device = "cpu"
local_model_path = "C:\\Users\\Administrator\\.cache\\huggingface\\openbmb\\MiniCPM3-4B"
tokenizer = AutoTokenizer.from_pretrained(local_model_path, trust_remote_code=True)
tokenizer.pad_token_id = tokenizer.eos_token_id if tokenizer.eos_token_id is not None else 0
model = AutoModelForCausalLM.from_pretrained(local_model_path, torch_dtype=torch.bfloat16, device_map=device, trust_remote_code=True)

# 初始化历史记录
history = []

from i_lab_flask import views, errors

@app.before_first_request
def create_tables():
    db.create_all()
