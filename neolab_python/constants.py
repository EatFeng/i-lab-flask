import os

class StatusCodes:
    OK = 200
    BAD_REQUEST = 400
    NOT_FOUND = 404
    INTERNAL_SERVER_ERROR = 500

class Config:
    # 数据库常量
    DATABASE_URI = os.environ.get('SQLALCHEMY_DATABASE_URI')
    TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get('SECRET_KEY')
    # 上传文件常量
    UPLOAD_FOLDER = 'F:/PythonProjects/neoLab/neolab_python/'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    # 聊天机器人常量
    DEVICE = "cpu"
    LOCAL_MODEL_PATH = "F:\\PythonProjects\\MiniCPM-1B"