from transformers import AutoModelForCausalLM, AutoTokenizer
from flask import Flask
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from paddlespeech.cli.tts.infer import TTSExecutor
from paddlespeech.cli.asr.infer import ASRExecutor
import torch
from constants import Config

app = Flask(__name__)
CORS(app)

# 配置数据库连接
app.config['SQLALCHEMY_DATABASE_URI'] = Config.DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = Config.TRACK_MODIFICATIONS
app.config['SECRET_KEY'] = Config.SECRET_KEY

# 配置上传文件参数
app.config['UPLOAD_FOLDER'] = Config.UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH

db = SQLAlchemy(app)
migrate = Migrate(app, db)

tts_executor = TTSExecutor()
asr_executor = ASRExecutor()

# 加载模型和分词器
device = Config.DEVICE
local_model_path = Config.LOCAL_MODEL_PATH
tokenizer = AutoTokenizer.from_pretrained(local_model_path, trust_remote_code=True)
tokenizer.pad_token_id = tokenizer.eos_token_id if tokenizer.eos_token_id is not None else 0
model = AutoModelForCausalLM.from_pretrained(local_model_path, torch_dtype=torch.bfloat16, device_map=device, trust_remote_code=True)

from i_lab_flask import views, errors, utils, config

@app.before_first_request
def create_tables():
    db.create_all()
