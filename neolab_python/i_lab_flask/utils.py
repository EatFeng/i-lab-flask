from constants import StatusCodes, Config
from flask import jsonify
from sqlalchemy import inspect
from datetime import  datetime
from zoneinfo import ZoneInfo
import base64
import os
from i_lab_flask import app

# 数据库会话提交和错误处理
def commit_session(db, error_status=StatusCodes.BAD_REQUEST, error_message='Failed to create a new lab.'):
    """
    提交数据库会话，处理事务。

    参数:
        - db (SQLAlchemy): SQLAlchemy数据库对象。
        - error_status (int): 发生错误时的HTTP状态码。
        - error_message (str): 发生错误时的错误消息。

    返回:
        - dict: 如果提交失败，返回包含错误信息的JSON响应；否则返回None。
    """
    try:
        db.session.commit()
        return None
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Database commit failed: {e}")
        return get_response(error_status, message=error_message)

# 查询数据库所有记录并返回JSON
def query_all_and_return_json(model, **filters):
    """
        查询数据库中所有符合条件的记录，并返回JSON响应。

        参数:
            - model (class): SQLAlchemy模型类。
            - **filters (dict): 查询过滤条件。

        返回:
            - tuple:
                - dict: JSON响应数据。
                - int: HTTP状态码。

        抛出:
            - None: 该函数不会抛出异常，但在查询不到记录时会返回404状态码。

        逻辑步骤:
            1. 添加默认的 `is_delete=False` 过滤条件。
            2. 根据提供的过滤条件查询数据库。
            3. 如果查询结果为空，返回404状态码和错误信息。
            4. 将查询结果转换为字典列表。
            5. 构建并返回JSON响应。
    """
    # 添加默认的 is_delete=False 过滤条件
    default_filters = {'is_delete': False}
    filters.update(default_filters)

    # 根据查询条件查询数据库，病返回JSON
    items = model.query.filter_by(**filters).all()
    if not items:
        return jsonify({'error': 'Items not found', 'state': StatusCodes.NOT_FOUND}), StatusCodes.NOT_FOUND

    # 将实例转为字典
    data = [item_to_dict(model, item) for item in items]

    # 返回JSON响应
    return get_response(status=StatusCodes.OK, data_num=len(items), data=data)

# 查询数据库一条记录并返回JSON
def query_one_and_return_json(model, **filters):
    """
    Query a single record from the database based on the given filters and return it as JSON.

    :param model: The SQLAlchemy model class.
    :param filters: Keyword arguments that are used as filters for the query.
    :return: A JSON response with the record data or an error message.
    """
    # 添加默认的 is_delete=False 过滤条件
    default_filters = {'is_delete': False}
    filters.update(default_filters)

    # 使用 filter_by 查找符合条件的第一条记录
    item = model.query.filter_by(**filters).first_or_404()
    if item is None:
        # 如果没有找到记录，返回 404 错误
        return jsonify({'error': 'Item not found', 'state': StatusCodes.NOT_FOUND}), StatusCodes.NOT_FOUND

    # 将模型实例转换为字典
    data = item_to_dict(model, item)

    # 返回 JSON 响应
    return get_response(status=StatusCodes.OK, data_num=1, data=data)

# 构建JSON中的data字典
def item_to_dict(model, instance, additional_fields=None):
    """
    将SQLAlchemy模型实例转换为字典。

    参数:
        - model (class): SQLAlchemy模型类。
        - instance (object): 模型实例。
        - additional_fields (dict, optional): 需要额外添加的字段及其值。

    返回:
        - dict: 包含模型实例属性的字典。
    """
    model_inspector = inspect(model)
    columns = model_inspector.columns
    data_dict = {column.key: getattr(instance, column.key) for column in columns if hasattr(instance, column.key)}

    if additional_fields:
        for key, value in additional_fields.items():
            if callable(value):
                data_dict[key] = value(instance)
            else:
                data_dict[key] = value

    return data_dict

def get_response(status, data=None, data_num=None, lab_number=None, message=None):
    """
    构建HTTP响应。

    参数:
        - status (int): HTTP状态码。
        - data (dict, optional): 响应数据。
        - data_num (int, optional): 数据数量。
        - lab_number (str, optional): 实验室编号。
        - message (str, optional): 错误或成功消息。

    返回:
        - tuple:
            - dict: JSON响应数据。
            - int: HTTP状态码。
    """
    response = {'state': status}
    if data is not None:
        response['data'] = data
    if data_num is not None:
        response['data_num'] = data_num
    if lab_number is not None:
        response['lab_number'] = lab_number
    if message is not None:
        response['massage'] = message
    return jsonify(response), status


# 获取当前时间的北京时间
def beijing_time_now():
    """
    获取当前北京时间。

    返回:
        - datetime.datetime: 当前北京时间。
    """
    return datetime.now(ZoneInfo("Asia/Shanghai"))

# 允许的音频文件格式
def allowed_audio_file(filename):
    """
    检查文件名是否为允许的音频文件格式。

    参数:
        - filename (str): 文件名。

    返回:
        - bool: 如果文件名符合允许的音频文件格式，则返回True；否则返回False。
    """
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in {'wav'}

# 允许的图片文件格式
def allowed_image_file(filename):
    """
    检查文件名是否为允许的图片文件格式。

    参数:
        - filename (str): 文件名。

    返回:
        - bool: 如果文件名符合允许的图片文件格式，则返回True；否则返回False。
    """
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

# 将图片转为base64图像源字符串
def image_to_base64(image_path):
    """
    将图片文件转换为Base64编码的字符串。

    参数:
        - image_path (str): 图片文件的路径。

    返回:
        - str: Base64编码的图片源字符串。

    抛出:
        - FileNotFoundError: 如果图片文件不存在。
        - ValueError: 如果图片文件格式不受支持。
    """
    if image_path is not None:
        # 检查文件是否存在
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image file not found: {image_path}")

        # 读取图片文件为二进制数据
        with open(image_path, "rb") as image_file:
            # 将二进制数据转换为Base64编码的字符串
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')

        # 获取文件扩展名
        file_extension = os.path.splitext(image_path)[1].lower()

        # 构建完整的Base64图像源字符串
        if file_extension == '.jpg' or file_extension == '.jpeg':
            mime_type = 'image/jpeg'
        elif file_extension == '.png':
            mime_type = 'image/png'
        else:
            raise ValueError("Unsupported image format")

        base64_image_source = f"data:{mime_type};base64,{encoded_string}"
    else:
        base64_image_source = ""

    return base64_image_source

def save_uploaded_file(file, filename):
    """
        保存上传的文件到指定目录。

        参数:
            - file (werkzeug.datastructures.FileStorage): 上传的文件对象。
            - filename (str): 文件名。

        返回:
            - str: 保存文件的完整路径。

        抛出:
            - FileNotFoundError: 如果上传文件夹不存在。
        """
    audio_file_path = os.path.join(Config.UPLOAD_FOLDER, filename)
    file.save(audio_file_path)
    return audio_file_path

def check_required_params(form, *params):
    """
    检查表单数据中是否存在并填写了指定的参数。

    参数:
        - form (dict): 表单数据字典。
        - *params (str): 需要检查的参数名称。

    返回:
        - tuple:
            - bool: 如果存在缺失的参数，返回True；否则返回False。
            - dict: 如果存在缺失的参数，返回包含错误信息的JSON响应；否则返回None。
    """
    for param in params:
        if param not in form or form[param].strip() == '':
            return True, get_response(status=StatusCodes.BAD_REQUEST, message=f'{param} is required')
    return False, None

