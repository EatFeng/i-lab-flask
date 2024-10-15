from flask import request, jsonify, send_file
import os
from i_lab_flask import app, db, tts_executor, asr_executor, tokenizer, model
from i_lab_flask.models import Lab, Guidance, ssi_Lab, Introductions
from i_lab_flask.config import Config
from werkzeug.utils import secure_filename
import tempfile
import json
from sqlalchemy import asc
import time
from constants import StatusCodes
from i_lab_flask.utils import query_all_and_return_json, query_one_and_return_json, commit_session, get_response
from i_lab_flask.utils import check_required_params, item_to_dict
from i_lab_flask.utils import allowed_image_file, allowed_audio_file, beijing_time_now
from i_lab_flask.utils import image_to_base64, save_uploaded_file
from errors import CustomError
from io import BytesIO
import logging

# 加载配置
app.config.from_object(Config)

# 配置日志
logging.basicConfig(level=getattr(logging, app.config['LOG_LEVEL']))
logger = logging.getLogger(__name__)


# 实验室管理页面
@app.route('/manage')
def manage():
    """
        获取所有未删除的实验室记录。

        请求方法: GET
        请求路径: /manage

        逻辑步骤:
            1. 查询所有 `is_delete=False` 的实验室记录。
            2. 将查询结果转换为字典列表。
            3. 构建并返回JSON响应。
        """
    return query_all_and_return_json(Lab, is_delete=False)

# 删除实验室
@app.route('/delete-lab/<int:lab_number>', methods=['POST'])
def delete_lab(lab_number):
    """
        删除指定编号的实验室记录，并将相关联的指导记录标记为已删除。

        请求方法: POST
        请求路径: /delete-lab/<int:lab_number>
        请求参数:
            - lab_number (int): 实验室编号。

        逻辑步骤:
            1. 查询指定编号的实验室记录。
            2. 如果实验室记录存在，将其 `is_delete` 字段设置为 `True`。
            3. 查询与该实验室ID关联的所有指导记录，并将它们的 `is_delete` 字段设置为 `True`。
            4. 提交数据库更改。
            5. 返回所有 `is_delete=False` 的实验室记录。
    """
    lab = Lab.query.filter_by(lab_number=lab_number).first()
    if lab:
        # 设置is_delete为1而不是删除记录
        lab.is_delete = True
        # 同时更新与该实验室ID关联的所有Guidance记录的is_delete字段
        related_guidances = Guidance.query.filter_by(lab_id=lab.id).all()
        for guidance in related_guidances:
            guidance.is_delete = True
        commit_session(db)
        # 删除成功后,返回所有is_delete=False的实验室记录
        return query_all_and_return_json(Lab, is_delete=False)
    else:
        # 如果实验室记录不存在，返回404状态码
        return get_response(StatusCodes.NOT_FOUND, message='Lab not found')

# 新建实验室页面
@app.route('/new_lab', methods=['POST'])
def new_lab():
    """
        创建新的实验室记录。

        请求方法: POST
        请求路径: /new_lab
        请求参数:
            - form:
                - lab_name (str): 实验室名称，必填。
                - lab_location (str): 实验室位置，必填。
                - lab_number (int): 实验室编号，必填。

        逻辑步骤:
            1. 从请求表单中获取实验室名称、位置和编号。
            2. 创建新的实验室记录并添加到数据库。
            3. 提交数据库更改。
            4. 返回所有 `is_delete=False` 的实验室记录。
    """
    if request.method == 'POST':
        lab_name = request.form['lab_name']
        lab_location = request.form['lab_location']
        lab_number = request.form['lab_number']
        new_lab = Lab(lab_name=lab_name, location=lab_location, lab_number=lab_number)
        db.session.add(new_lab)
        commit_session(db)
        return query_all_and_return_json(Lab, is_delete=False)

# 进入实验室页面
@app.route('/lab/<int:lab_number>', methods=['GET', 'POST'])
def lab(lab_number):
    """
        处理实验室页面的请求，包括获取实验室信息、更新实验室信息、添加和更新指导信息。

        请求方法: GET, POST
        请求路径: /lab/<int:lab_number>

        参数:
            - lab_number (int): 实验室编号。

        表单参数 (POST):
            - action (str): 操作类型，可以是 'update_lab', 'add_guidance', 'update_guidance'。
            - lab_name (str): 实验室名称（仅在 'update_lab' 时需要）。
            - lab_location (str): 实验室位置（仅在 'update_lab' 时需要）。
            - point_id (int): 指导点ID（仅在 'add_guidance', 'update_guidance' 时需要）。
            - topic (str): 指导主题（仅在 'add_guidance', 'update_guidance' 时需要）。
            - content (str): 指导内容（仅在 'add_guidance', 'update_guidance' 时需要）。
            - audio_path (str): 音频文件路径（仅在 'add_guidance', 'update_guidance' 时需要）。
            - guidance_id (int): 指导记录ID（仅在 'update_guidance' 时需要）。

        响应:
            - 成功:
                - HTTP状态码: 200
                - JSON响应: 包含实验室或指导信息的JSON对象。
            - 失败:
                - HTTP状态码: 404 (Not Found)
                - JSON响应: 包含错误信息的JSON对象。
                - HTTP状态码: 400 (Bad Request)
                - JSON响应: 包含错误信息的JSON对象。

        逻辑步骤:
            1. 获取指定编号的实验室记录，如果不存在则返回404。
            2. 如果是POST请求：
                - 根据 `action` 参数执行相应操作：
                    - 'update_lab': 更新实验室信息。
                    - 'add_guidance': 添加新的指导记录。
                    - 'update_guidance': 更新现有指导记录。
            3. 如果是GET请求：
                - 查询该实验室的所有未删除的指导记录，并按 `point_id` 升序排序。
                - 返回包含指导信息的JSON响应。
        """
    lab = Lab.query.filter_by(lab_number=lab_number).first_or_404()

    if request.method == 'POST':
        form_data = request.form
        action = form_data.get('action')

        if action == 'update_lab':
            lab.lab_name = request.form['lab_name']
            lab.location = request.form['lab_location']
            commit_session(db)
            return query_one_and_return_json(Lab, lab_number=lab_number)

        elif action == 'add_guidance':
            new_guidance = Guidance(
                lab_number=lab.lab_number,
                point_id=form_data['point_id'],
                topic=form_data['topic'],
                content=form_data['content'],
                audio_path=form_data['audio_path']
            )
            db.session.add(new_guidance)
            commit_session(db)
            return query_one_and_return_json(Guidance,
                                             lab_number=new_guidance.lab_number, point_id=new_guidance.point_id)

        elif action == 'update_guidance':
            guidance_id = request.form['guidance_id']
            guidance = Guidance.query.get(guidance_id)
            if guidance:
                guidance.point_id = form_data['point_id']
                guidance.topic = form_data['topic']
                guidance.content = form_data['content']
                guidance.audio_path = form_data['audio_path']
                commit_session(db)
                return query_one_and_return_json(Guidance,
                                                 lab_number=guidance.lab_number, point_id=guidance.point_id)
            else:
                return get_response(StatusCodes.NOT_FOUND, 0, {'message': 'Guidance not found'})
                # 如果 action 不是上述任何一个，返回错误响应

        return get_response(StatusCodes.BAD_REQUEST, 0, {'message': 'Invalid action'})

    else:
        guidance = Guidance.query.filter_by(lab_number=lab_number, is_delete=False).order_by(
            asc(Guidance.point_id)).all()
        response_data = [
            {
                'point_id': g.point_id,
                'topic': g.topic,
                'content': g.content,
                'path': g.audio_path
            } for g in guidance
        ]
        return get_response(StatusCodes.OK, len(guidance), response_data, lab_number)

# 删除讲解请求
@app.route('/lab/<int:lab_number>/delete-guidance/<int:point_id>', methods=['POST'])
def delete_guidance(lab_number, point_id):
    """
        删除指定实验室编号和指导点ID的指导记录，并将其标记为已删除。

        请求方法: POST
        请求路径: /lab/<int:lab_number>/delete-guidance/<int:point_id>

        参数:
            - lab_number (int): 实验室编号。
            - point_id (int): 指导点ID。

        响应:
            - 成功:
                - HTTP状态码: 200
                - JSON响应: 包含所有未删除的指导记录的JSON对象。
            - 失败:
                - HTTP状态码: 404 (Not Found)
                - JSON响应: 包含错误信息的JSON对象。

        逻辑步骤:
            1. 查询指定实验室编号和指导点ID的指导记录，如果记录不存在则返回404。
            2. 如果记录存在，将其 `is_delete` 字段设置为 `True`。
            3. 提交数据库更改。
            4. 查询所有 `is_delete=False` 的指导记录，并返回这些记录的JSON响应。
    """
    guidance = Guidance.query.filter_by(lab_number=lab_number, point_id=point_id, is_delete=False).first_or_404()
    if guidance:
        # 设置is_delete为1而不是删除记录
        guidance.is_delete = 1
        db.session.commit()
        # 查询所有is_delete为False的guidance记录
        return query_all_and_return_json(Guidance, lab_number=lab_number, is_delete=False)
    else:
        # 如果guidance记录不存在，返回404状态码
        return get_response(StatusCodes.NOT_FOUND, 0, {'message': 'Guidance not found'}), 404

# 生成语音请求
@app.route('/lab/generate-audio/<int:lab_number>/<int:point_id>', methods=['GET'])
def generate_audio(lab_number, point_id):
    """
    生成指定实验室编号和指导点ID的指导记录的音频文件。

    请求方法: GET
    请求路径: /lab/generate-audio/<int:lab_number>/<int:point_id>

    参数:
        - lab_number (int): 实验室编号。
        - point_id (int): 指导点ID。

    响应:
        - 成功:
            - HTTP状态码: 200
            - JSON响应: 包含更新后的指导记录的JSON对象。
        - 失败:
            - HTTP状态码: 404 (Not Found)
            - JSON响应: 包含错误信息的JSON对象。
            - HTTP状态码: 500 (Internal Server Error)
            - JSON响应: 包含错误信息的JSON对象。

    逻辑步骤:
        1. 查询指定实验室编号和指导点ID的指导记录，如果记录不存在则返回404。
        2. 如果记录存在，删除旧的音频文件（如果存在）。
        3. 生成新的音频文件并保存到指定路径。
        4. 更新数据库中的音频路径。
        5. 返回更新后的指导记录的JSON响应。
    """
    try:
        # 查询Guidance表中的记录
        guidance = Guidance.query.filter_by(lab_number=lab_number, point_id=point_id, is_delete=False).first_or_404()
        if guidance:
            # 删除旧的音频文件
            if guidance.audio_path is not None and guidance.audio_path.endswith('.wav'):
                os.remove(guidance.audio_path)

            # 生成音频
            timestamp = int(time.time())  # 获取当前时间戳
            audio_file_name = f'{guidance.lab_number}_{guidance.point_id}_{timestamp}.wav'
            audio_file_path = 'i_lab_flask/output/' + audio_file_name
            tts_executor(text=guidance.content, output=audio_file_path)

            # 更新数据库
            guidance.audio_path = audio_file_path
            commit_session(db)

            # 查询该记录
            return query_one_and_return_json(Guidance, lab_number=lab_number, point_id=point_id, is_delete=False)
        else:
            # 如果guidance记录不存在，返回404状态码
            return get_response(StatusCodes.NOT_FOUND, 0, {'error_message': 'Guidance not found'}), 404

    except Exception as e:
        app.logger.error(f"Error occurred: {e}")
        return get_response(StatusCodes.INTERNAL_SERVER_ERROR, 0, {'error_message': 'Internal server error'}), 500

# 获取音频文件
@app.route('/lab/get-audio/<int:lab_number>/<int:point_id>', methods=['GET'])
def get_audio(lab_number, point_id):
    """
    获取指定实验室编号和指导点ID的指导记录的音频文件。

    请求方法: GET
    请求路径: /lab/get-audio/<int:lab_number>/<int:point_id>

    参数:
        - lab_number (int): 实验室编号。
        - point_id (int): 指导点ID。

    响应:
        - 成功:
            - HTTP状态码: 200
            - 文件响应: 包含音频文件。
        - 失败:
            - HTTP状态码: 404 (Not Found)
            - JSON响应: 包含错误信息的JSON对象。

    逻辑步骤:
        1. 查询指定实验室编号和指导点ID的指导记录，如果记录不存在则返回404。
        2. 检查数据库中是否保存该记录的音频路径，如果不存在则返回404。
        3. 确保音频文件存在，如果不存在则返回404。
        4. 返回音频文件。
    """
    # 在Guidance模型中检索匹配的记录
    guidance = Guidance.query.filter_by(point_id=point_id, lab_number=lab_number, is_delete=False).first_or_404()

    # 检查数据库中是否保存该记录的音频路径
    if guidance.audio_path is None:
        return get_response(StatusCodes.NOT_FOUND, 0, {'error_message': 'File path not exist.'}), 404

    # 确保文件存在
    audio_file_path = os.path.join(app.config['UPLOAD_FOLDER'], guidance.audio_path)
    print(audio_file_path)
    if not os.path.isfile(audio_file_path):
        return get_response(StatusCodes.NOT_FOUND, 0, {'error_message': 'Audio file not found.'}), 404

    # 返回音频文件
    return send_file(str(audio_file_path), as_attachment=True, download_name=secure_filename(guidance.audio_path))

# 上传音频文件
@app.route('/upload_audio', methods=['POST'])
def upload_audio():
    """
    上传音频文件并更新指定实验室编号和指导点ID的指导记录。

    请求方法: POST
    请求路径: /upload_audio

    表单参数:
        - file (file): 音频文件。
        - point_id (int): 指导点ID。
        - lab_number (int): 实验室编号。

    响应:
        - 成功:
            - HTTP状态码: 200
            - JSON响应: 包含成功信息和音频文件路径的JSON对象。
        - 失败:
            - HTTP状态码: 400 (Bad Request)
            - JSON响应: 包含错误信息的JSON对象。
            - HTTP状态码: 404 (Not Found)
            - JSON响应: 包含错误信息的JSON对象。

    逻辑步骤:
        1. 检查请求中是否包含文件。
        2. 检查必填字段 `point_id` 和 `lab_number` 是否存在。
        3. 检查文件类型是否允许。
        4. 保存上传的文件到指定路径。
        5. 查找匹配的记录并更新 `is_delete` 字段。
        6. 保存新的指导记录到数据库。
        7. 返回包含成功信息和音频文件路径的JSON响应。
    """
    # 检查是否有文件在请求中
    if 'file' not in request.files:
        return get_response(StatusCodes.BAD_REQUEST, 'No file part in the request')

    file = request.files['file']
    point_id = request.form.get('point_id')
    lab_number = request.form.get('lab_number')

    # 检查必填字段
    if file is None or file.filename == '':
        return get_response(StatusCodes.BAD_REQUEST, 'No selected file')

    if point_id is None or point_id.strip() == '':
        return get_response(StatusCodes.BAD_REQUEST, 'point_id is required')

    if lab_number is None or lab_number.strip() == '':
        return get_response(StatusCodes.BAD_REQUEST, 'lab_number is required')

    if not allowed_audio_file(file.filename):
        return get_response(StatusCodes.BAD_REQUEST, 'File type not allowed')

    # 保存文件
    filename = 'i_lab_flask/upload/' + secure_filename(file.filename)
    audio_file_path = save_uploaded_file(file, filename)

    # 查找匹配的记录并更新is_delete
    existing_guidance = Guidance.query.filter_by(point_id=point_id, lab_number=lab_number, is_delete=False).first()
    if existing_guidance:
        existing_guidance.is_delete = True
        content = existing_guidance.content
        topic = existing_guidance.topic
        db.session.commit()
    else:
        return get_response(StatusCodes.NOT_FOUND, 'Guidance Record not found')

    # 保存记录到数据库
    new_guidance = Guidance(point_id=point_id,
                            lab_number=lab_number,
                            topic = topic,
                            content = content,
                            audio_path=filename)
    db.session.add(new_guidance)
    db.session.commit()

    return get_response(StatusCodes.OK, 'File uploaded successfully', data={'path': audio_file_path})

# 发送讲解内容
@app.route('/get_guidance_content/', methods=['POST'])
def get_guidance_content():
    """
    发送指定实验室编号和指导点ID的指导内容。

    请求方法: POST
    请求路径: /get_guidance_content/

    表单参数:
        - lab_number (int): 实验室编号。
        - point_id (int): 指导点ID。

    响应:
        - 成功:
            - HTTP状态码: 200
            - JSON响应: 包含指导内容的JSON对象。
        - 失败:
            - HTTP状态码: 400 (Bad Request)
            - JSON响应: 包含错误信息的JSON对象。
            - HTTP状态码: 404 (Not Found)
            - JSON响应: 包含错误信息的JSON对象。

    逻辑步骤:
        1. 检查请求中是否包含必填字段 `lab_number` 和 `point_id`。
        2. 查询指定实验室编号和指导点ID的指导记录。
        3. 检查是否找到记录，如果未找到则返回404。
        4. 检查 `content` 字段是否为 `null` 或者内容为空，如果是则返回404。
        5. 构建包含指导内容的JSON响应并返回。
    """
    # 检查必填字段
    missing, error_response = check_required_params(request.form, 'lab_number', 'point_id')
    if missing:
        return error_response

    point_id = request.form['point_id']
    lab_number = request.form['lab_number']

    # 在Guidance模型中检索匹配的记录
    guidance = Guidance.query.filter_by(point_id=point_id, lab_number=lab_number).first()

    # 检查是否找到记录
    if guidance is None:
        return get_response(status=StatusCodes.NOT_FOUND, message='Guidance not found')

    # 检查content字段是否为null或者非null但是内容为空
    if guidance.content is None or (guidance.content is not None and not guidance.content.strip()):
        return get_response(status=StatusCodes.NOT_FOUND, message='Content is empty or null')

    # 返回content字段数据的JSON
    response = {
        'point_id': guidance.point_id,
        'lab_number': guidance.lab_number,
        'content': guidance.content
    }
    return get_response(status=StatusCodes.OK, message='Content retrieved successfully', data=response)

# --------------------- 小屏介绍管理页 --------------------- #
# 小屏介绍页面
@app.route('/ssi/manage')
def ssi_manage():
    """
    获取所有未删除的小屏实验室记录。

    请求方法: GET
    请求路径: /ssi/manage

    响应:
        - 成功:
            - HTTP状态码: 200
            - JSON响应: 包含所有未删除的小屏实验室记录的JSON对象。
    """
    return query_all_and_return_json(ssi_Lab, is_delete=False)

# 小屏讲解管理页 -> 新建
@app.route('/ssi/new_lab', methods=['POST'])
def ssi_new_lab():
    """
    创建一个新的小屏实验室记录。

    请求方法: POST
    请求路径: /ssi/new_lab

    表单参数:
        - lab_name (str): 实验室名称。
        - lab_location (str): 实验室位置。
        - lab_number (int): 实验室编号。

    响应:
        - 成功:
            - HTTP状态码: 200
            - JSON响应: 包含新创建的实验室记录的JSON对象。
        - 失败:
            - HTTP状态码: 400 (Bad Request)
            - JSON响应: 包含错误信息的JSON对象。
            - HTTP状态码: 409 (Conflict)
            - JSON响应: 包含错误信息的JSON对象。
    """
    # 检查必填参数
    missing, error_response = check_required_params(request.form, 'lab_name', 'lab_location', 'lab_number')
    if missing:
        return error_response

    # 获取表单数据
    lab_name = request.form['lab_name']
    lab_location = request.form['lab_location']
    lab_number = request.form['lab_number']

    # 创建新实验室对象
    new_ssi_lab = ssi_Lab(
        lab_name=lab_name,
        location=lab_location,
        lab_number=lab_number,
        create_time=beijing_time_now(),
        update_time=beijing_time_now()
    )

    # 尝试将新实验室对象保存到数据库
    result = commit_session(db, StatusCodes.BAD_REQUEST, 'Lab number already exists.')
    if result:
        return jsonify(result), result['state']

    # 创建成功后，返回实验室的信息
    return get_response(
        status=StatusCodes.OK,
        data=item_to_dict(ssi_Lab, new_ssi_lab),
        data_num=1
    )

# 小屏讲解管理页 -> 删除
@app.route('/ssi/delete_lab/<int:lab_number>', methods=['POST'])
def ssi_delete_lab(lab_number):
    """
    删除指定实验室编号的小屏实验室记录，并将其标记为已删除。

    请求方法: POST
    请求路径: /ssi/delete_lab/<int:lab_number>

    参数:
        - lab_number (int): 实验室编号。

    响应:
        - 成功:
            - HTTP状态码: 200
            - JSON响应: 包含所有未删除的小屏实验室记录的JSON对象。
        - 失败:
            - HTTP状态码: 404 (Not Found)
            - JSON响应: 包含错误信息的JSON对象。
            - HTTP状态码: 500 (Internal Server Error)
            - JSON响应: 包含错误信息的JSON对象。
    """
    ssi_lab = ssi_Lab.query.filter_by(lab_number=lab_number).first()

    if not ssi_lab:
        return get_response(StatusCodes.NOT_FOUND, 0, {'error_message': 'Lab not found'})

    # 设置is_delete为1而不是删除记录
    ssi_lab.is_delete = True
    ssi_lab.update_time = beijing_time_now()

    # 同时更新与该实验室ID关联的所有Guidance记录的is_delete字段
    related_intros = Introductions.query.filter_by(lab_number=ssi_Lab.lab_number).all()
    for intro in related_intros:
        intro.is_delete = True

    # 尝试提交更改
    result = commit_session(db, StatusCodes.INTERNAL_SERVER_ERROR, 'Failed to delete lab.')
    if result:
        return jsonify(result), result['state']

    # 获取所有is_delete为False的实验室记录
    ssi_labs = ssi_Lab.query.filter_by(is_delete=False).all()
    labs_data = [item_to_dict(ssi_Lab, lab) for lab in ssi_labs]

    # 返回JSON响应
    return get_response(status=StatusCodes.OK, data=labs_data, data_num=len(ssi_labs))

# 小屏讲解管理页 -> 编辑
@app.route('/ssi/update_lab/<int:lab_number>', methods=['POST'])
def ssi_update_lab(lab_number):
    """
    更新指定实验室编号的小屏实验室记录。

    请求方法: POST
    请求路径: /ssi/update_lab/<int:lab_number>

    参数:
        - lab_number (int): 实验室编号。

    表单参数:
        - update_lab (str): 必须为 'true'。
        - lab_name (str): 实验室名称。
        - lab_location (str): 实验室位置。

    响应:
        - 成功:
            - HTTP状态码: 200
            - JSON响应: 包含更新后的实验室记录的JSON对象。
        - 失败:
            - HTTP状态码: 400 (Bad Request)
            - JSON响应: 包含错误信息的JSON对象。
            - HTTP状态码: 404 (Not Found)
            - JSON响应: 包含错误信息的JSON对象。
            - HTTP状态码: 500 (Internal Server Error)
            - JSON响应: 包含错误信息的JSON对象。
    """
    # 从表单中获取数据
    form = request.form

    # 检查表单中是否有update_lab字段
    if 'update_lab' not in form or form['update_lab'].strip().lower() != 'true':
        return get_response(StatusCodes.BAD_REQUEST, message='Invalid request: check the field update_lab.')

    # 检查必填参数
    missing, error_response = check_required_params(form, 'lab_name', 'lab_location')
    if missing:
        return error_response

    # 获取表单数据
    lab_name = form['lab_name']
    lab_location = form['lab_location']

    # 根据实验室编号查找实验室
    lab = ssi_Lab.query.filter_by(lab_number=lab_number).first()
    if not lab:
        # 如果找不到实验室记录，返回404状态码
        return get_response(StatusCodes.NOT_FOUND, message='Lab not found.')

    # 更新实验室信息
    lab.lab_name = lab_name
    lab.location = lab_location
    lab.update_time = beijing_time_now()

    # 尝试提交修改
    result = commit_session(db, StatusCodes.INTERNAL_SERVER_ERROR, 'Failed to update lab.')
    if result:
        return jsonify(result), result['state']

    # 返回更新后的实验室信息
    return get_response(
        status=StatusCodes.OK,
        message='Lab updated successfully.',
        data=item_to_dict(ssi_Lab, lab)
    )


# 小屏讲解管理页 -> 详情
@app.route('/ssi/lab/<int:lab_number>', methods=['GET'])
def ssi_lab(lab_number):
    """
    获取指定实验室编号的小屏实验室详情及其介绍记录。

    请求方法: GET
    请求路径: /ssi/lab/<int:lab_number>

    参数:
        - lab_number (int): 实验室编号。

    响应:
        - 成功:
            - HTTP状态码: 200
            - JSON响应: 包含实验室详情和介绍记录的JSON对象。
        - 失败:
            - HTTP状态码: 400 (Bad Request)
            - JSON响应: 包含错误信息的JSON对象。
            - HTTP状态码: 404 (Not Found)
            - JSON响应: 包含错误信息的JSON对象。
            - HTTP状态码: 500 (Internal Server Error)
            - JSON响应: 包含错误信息的JSON对象。

    逻辑步骤:
        1. 检查 `lab_number` 是否存在。
        2. 查询 `ssi_Lab` 表中的记录，如果记录不存在则返回404。
        3. 查询 `Introductions` 表中的记录，如果记录不存在则返回404。
        4. 构建实验室数据和介绍数据的JSON响应。
        5. 返回JSON响应。
    """
    if lab_number is None:
        return get_response(StatusCodes.BAD_REQUEST, message='Missing lab_number parameter')

    try:
        # 查询ssi_Lab表中的记录
        lab = ssi_Lab.query.filter_by(lab_number=lab_number, is_delete=False).first()
        if not lab:
            return jsonify({'error': 'Lab not found', 'state': 404}), 404

        # 查询Introductions表中的记录
        intros = Introductions.query.filter_by(lab_number=lab_number, is_delete=False).all()
        if not intros:
            return get_response(StatusCodes.NOT_FOUND, message='introduction not found')

        # 构建实验室数据
        lab_data = item_to_dict(ssi_Lab, lab,
                                additional_fields={
                                    'img_segmentation': lambda lab:image_to_base64(lab.img_segmentation),
                                    'img_total': lambda lab: image_to_base64(lab.img_total),
                                    'create_time': lambda lab: lab.create_time.isoformat(),
                                    'update_time': lambda lab: lab.update_time.isoformat()
                                })
        # 构建介绍数据
        intros_data = [
            item_to_dict(
                Introductions, intro,
                additional_fields={
                    'image_path': lambda intro: image_to_base64(intro.image_path) if intro.image_path else None,
                    'update_time': lambda intro: intro.update_time.isoformat() if intro.update_time else None
                }
            )
            for intro in intros
        ]

        return get_response(
            status=StatusCodes.OK ,
            lab=lab_data,
            data=intros_data)

    except Exception as e:
        app.logger.error(f"Error occurred: {e}")
        return get_response(StatusCodes.INTERNAL_SERVER_ERROR, message='Internal server error')

# 小屏讲解管理页 -> 详情 -> 新建
@app.route('/ssi/add_intro/<int:lab_number>', methods=['POST'])
def add_intro(lab_number):
    """
    为指定实验室编号的小屏实验室添加新的介绍记录。

    请求方法: POST
    请求路径: /ssi/add_intro/<int:lab_number>

    参数:
        - lab_number (int): 实验室编号。

    表单参数:
        - summary (str): 介绍摘要。
        - details (str): 详细介绍。

    响应:
        - 成功:
            - HTTP状态码: 200
            - JSON响应: 包含新创建的介绍记录的JSON对象。
        - 失败:
            - HTTP状态码: 400 (Bad Request)
            - JSON响应: 包含错误信息的JSON对象。
            - HTTP状态码: 500 (Internal Server Error)
            - JSON响应: 包含错误信息的JSON对象。

    逻辑步骤:
        1. 检查表单中是否包含必填字段 `summary` 和 `details`。
        2. 获取当前时间。
        3. 创建新的介绍记录并保存到数据库。
        4. 返回新创建的介绍记录的JSON响应。
    """
    # 从表单中获取数据
    form = request.form

    # 检查必需参数
    missing_params, response = check_required_params(form, 'summary', 'details')
    if missing_params:
        return response

    # 从表单中获取数据
    summary = form['summary']
    details = form['details']

    # 获取当前时间
    current_time = beijing_time_now()

    # 创建新的记录
    new_intro = Introductions(
        lab_number=lab_number,
        time_line=current_time,
        summary=summary,
        details=details,
        update_time=current_time
    )

    # 将记录添加到数据库
    db.session.add(new_intro)

    # 提交会话
    result = commit_session(db, StatusCodes.INTERNAL_SERVER_ERROR, 'Failed to add introduction')
    if result:
        return result

    # 构建新记录的数据字典
    intro_data = item_to_dict(
        Introductions, new_intro,
        additional_fields={
            'time_line': lambda intro: intro.time_line.isoformat(),
            'update_time': lambda intro: intro.update_time.isoformat() if intro.update_time else None
        }
    )

    return get_response(
        status=StatusCodes.OK,
        data=intro_data
    )

# 小屏讲解管理页 -> 详情 -> 编辑
@app.route('/ssi/update_intro/<int:point_id>', methods=['POST'])
def update_intro(point_id):
    """
    更新指定介绍ID的小屏实验室介绍记录。

    请求方法: POST
    请求路径: /ssi/update_intro/<int:point_id>

    参数:
        - point_id (int): 介绍记录ID。

    表单参数:
        - summary (str): 介绍摘要。
        - details (str): 详细介绍。

    响应:
        - 成功:
            - HTTP状态码: 200
            - JSON响应: 包含更新后的介绍记录的JSON对象。
        - 失败:
            - HTTP状态码: 400 (Bad Request)
            - JSON响应: 包含错误信息的JSON对象。
            - HTTP状态码: 404 (Not Found)
            - JSON响应: 包含错误信息的JSON对象。
            - HTTP状态码: 500 (Internal Server Error)
            - JSON响应: 包含错误信息的JSON对象。

    逻辑步骤:
        1. 检查表单中是否包含必填字段 `summary` 和 `details`。
        2. 查询指定ID的介绍记录，如果记录不存在则返回404。
        3. 更新介绍记录的 `summary`、`details` 和 `update_time` 字段。
        4. 返回更新后的介绍记录的JSON响应。
    """
    # 从表单中获取数据
    form = request.form

    # 检查必需参数
    missing_params, response = check_required_params(form, 'summary', 'details')
    if missing_params:
        return response

    # 获取当前时间
    current_time = beijing_time_now()

    # 查询匹配的记录
    intro = Introductions.query.filter_by(id=point_id).first()
    if intro is None:
        return get_response(StatusCodes.NOT_FOUND, message='Introduction not found')

    # 更新记录
    intro.summary = form['summary']
    intro.details = form['details']
    intro.update_time = current_time

    # 提交会话
    result = commit_session(db, StatusCodes.INTERNAL_SERVER_ERROR, 'Failed to update introduction')
    if result:
        return result

    # 构建更新后的记录的数据字典
    intro_data = item_to_dict(
        Introductions, intro,
        additional_fields={
            'time_line': lambda intro: intro.time_line.isoformat(),
            'update_time': lambda intro: intro.update_time.isoformat() if intro.update_time else None
        }
    )

    return get_response(
        status=StatusCodes.OK,
        data=intro_data
    )

# 小屏讲解管理页 -> 详情 -> 删除
@app.route('/ssi/delete_intro/<int:point_id>/<int:lab_number>', methods=['POST'])
def delete_intro(point_id, lab_number):
    """
    删除指定介绍ID的小屏实验室介绍记录，并将其标记为已删除。

    请求方法: POST
    请求路径: /ssi/delete_intro/<int:point_id>/<int:lab_number>

    参数:
        - point_id (int): 介绍记录ID。
        - lab_number (int): 实验室编号。

    响应:
        - 成功:
            - HTTP状态码: 200
            - JSON响应: 包含所有未删除的介绍记录的JSON对象。
        - 失败:
            - HTTP状态码: 404 (Not Found)
            - JSON响应: 包含错误信息的JSON对象。
            - HTTP状态码: 500 (Internal Server Error)
            - JSON响应: 包含错误信息的JSON对象。

    逻辑步骤:
        1. 查询指定ID和实验室编号的介绍记录，如果记录不存在或已删除则返回404。
        2. 更新介绍记录的 `is_delete` 字段。
        3. 查询实验室编号匹配且 `is_delete` 为 `False` 的所有介绍记录。
        4. 返回所有未删除的介绍记录的JSON响应。
    """
    # 查询匹配的记录
    intro = Introductions.query.filter_by(id=point_id, lab_number=lab_number, is_delete=False).first()
    if intro is None:
        return get_response(StatusCodes.NOT_FOUND, message='Introduction not found or already deleted')

    # 更新is_delete字段
    intro.is_delete = True

    # 提交会话
    result = commit_session(db, StatusCodes.INTERNAL_SERVER_ERROR, 'Failed to delete introduction')
    if result:
        return result

    # 查询lab_number匹配且is_delete为False的所有记录
    intros_data = query_all_and_return_json(Introductions, lab_number=lab_number, is_delete=False)

    return intros_data

# 小屏讲解管理页 -> 详情 -> 获取照片
@app.route('/ssi/get_image/<int:lab_number>/<int:point_id>', methods=['GET'])
def get_image(lab_number, point_id):
    """
    获取指定实验室编号和介绍点ID的介绍记录的图片文件。

    请求方法: GET
    请求路径: /ssi/get_image/<int:lab_number>/<int:point_id>

    参数:
        - lab_number (int): 实验室编号。
        - point_id (int): 介绍点ID。

    响应:
        - 成功:
            - HTTP状态码: 200
            - 文件响应: 包含图片文件。
        - 失败:
            - HTTP状态码: 404 (Not Found)
            - JSON响应: 包含错误信息的JSON对象。

    逻辑步骤:
        1. 查询指定实验室编号和介绍点ID的介绍记录，如果记录不存在或没有图片路径则返回404。
        2. 构建图片文件的路径。
        3. 检查图片文件是否存在，如果不存在则返回404。
        4. 返回图片文件。
    """
    # 查询匹配的记录
    intro = Introductions.query.filter_by(lab_number=lab_number, point_id=point_id, is_delete=False).first()
    if intro is None or not intro.image_path:
        return get_response(StatusCodes.NOT_FOUND, message='Image not found')

    # 构建图片文件的路径
    image_file_path = os.path.join(app.config['UPLOAD_FOLDER'], intro.image_path)

    # 检查图片文件是否存在
    if not os.path.isfile(image_file_path):
        return get_response(StatusCodes.NOT_FOUND, message='Image file not found')

    # 返回图片文件
    return send_file(str(image_file_path), mimetype='image/png')

# 小屏讲解管理页 -> 详情 -> 上传照片
@app.route('/ssi/upload_image/<int:lab_number>/<int:point_id>', methods=['POST'])
def upload_image(lab_number, point_id):
    """
    上传图片文件并更新指定实验室编号和介绍点ID的介绍记录的图片路径。

    请求方法: POST
    请求路径: /ssi/upload_image/<int:lab_number>/<int:point_id>

    参数:
        - lab_number (int): 实验室编号。
        - point_id (int): 介绍点ID。

    表单参数:
        - image (file): 图片文件。

    响应:
        - 成功:
            - HTTP状态码: 200
            - JSON响应: 包含成功信息和图片路径的JSON对象。
        - 失败:
            - HTTP状态码: 400 (Bad Request)
            - JSON响应: 包含错误信息的JSON对象。
            - HTTP状态码: 404 (Not Found)
            - JSON响应: 包含错误信息的JSON对象。
            - HTTP状态码: 500 (Internal Server Error)
            - JSON响应: 包含错误信息的JSON对象。

    逻辑步骤:
        1. 检查请求中是否包含图片文件。
        2. 检查文件类型是否允许。
        3. 保存上传的图片文件到指定路径。
        4. 查询指定实验室编号和介绍点ID的介绍记录，如果记录不存在则返回404。
        5. 更新介绍记录的 `image_path` 字段。
        6. 返回包含成功信息和图片路径的JSON响应。
    """
    # 检查是否有文件在请求中
    if 'image' not in request.files:
        return get_response(StatusCodes.BAD_REQUEST, message='No image part in the request')

    file = request.files['image']
    if file.filename == '':
        return get_response(StatusCodes.BAD_REQUEST, message='No selected file')

    if file and allowed_image_file(file.filename):
        filename = 'i_lab_flask/images/' + secure_filename(file.filename)
        image_file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(image_file_path)

        # 查询匹配的记录
        intro = Introductions.query.filter_by(lab_number=lab_number, point_id=point_id, is_delete=False).first()
        if intro is None:
            return get_response(StatusCodes.NOT_FOUND, message='Introduction not found')

        # 更新image_path字段
        intro.image_path = image_file_path

        # 提交会话
        result = commit_session(db, StatusCodes.INTERNAL_SERVER_ERROR, 'Failed to update image path')
        if result:
            return result

        return get_response(
            StatusCodes.OK,
            message='Image uploaded and path updated successfully',
            data={'path': image_file_path}
        )

    else:
        return get_response(StatusCodes.BAD_REQUEST, message='File type not allowed')

# 小屏介绍-lab_number+point_id
@app.route('/ssi/lab/<int:lab_number>/<int:point_id>', methods=['GET'])
def get_introduction(lab_number, point_id):
    """
    获取指定实验室编号和介绍点ID的介绍记录的详细信息。

    请求方法: GET
    请求路径: /ssi/lab/<int:lab_number>/<int:point_id>

    参数:
        - lab_number (int): 实验室编号。
        - point_id (int): 介绍点ID。

    响应:
        - 成功:
            - HTTP状态码: 200
            - JSON响应: 包含介绍记录的详细信息的JSON对象。
        - 失败:
            - HTTP状态码: 404 (Not Found)
            - JSON响应: 包含错误信息的JSON对象。
            - HTTP状态码: 500 (Internal Server Error)
            - JSON响应: 包含错误信息的JSON对象。

    逻辑步骤:
        1. 查询指定实验室编号和介绍点ID的介绍记录，如果记录不存在则返回404。
        2. 将 `image_path` 转换为 base64 编码的字符串。
        3. 构建包含介绍记录详细信息的JSON响应。
        4. 返回JSON响应。
    """
    try:
        # 查询Introductions表中的记录
        intro = Introductions.query.filter_by(lab_number=lab_number, point_id=point_id, is_delete=False).first()
        if not intro:
            if not intro:
                return get_response(StatusCodes.NOT_FOUND, message='Introduction not found')

        # 将image_path转为base64
        image_base64 = image_to_base64(intro.image_path) if intro.image_path else None

        # 构建返回的数据
        intro_data = item_to_dict(
            Introductions, intro,
            additional_fields={
                'image_path': lambda intro: image_base64,
                'time_line': lambda intro: intro.time_line.isoformat(),
                'update_time': lambda intro: intro.update_time.isoformat() if intro.update_time else None
            }
        )

        return get_response(
            status=StatusCodes.OK,
            data=intro_data
        )

    except Exception as e:
        app.logger.error(f"Error occurred: {e}")
        return get_response(StatusCodes.INTERNAL_SERVER_ERROR, message='Internal server error')

# 移动端 -> 上传/修改
@app.route('/mobile/edit_lab/<int:lab_number>', methods=['POST'])
def update_ssi_lab(lab_number):
    """
    更新指定实验室编号的小屏实验室记录。

    请求方法: POST
    请求路径: /mobile/edit_lab/<int:lab_number>

    参数:
        - lab_number (int): 实验室编号。

    表单参数:
        - ico_path (str, 可选): 实验室图标路径。
        - room_num (str, 可选): 实验室房间号。
        - introduction (str, 可选): 实验室简介。
        - article (str, 可选): 实验室文章内容。

    响应:
        - 成功:
            - HTTP状态码: 200
            - JSON响应: 包含更新后的实验室记录的JSON对象。
        - 失败:
            - HTTP状态码: 404 (Not Found)
            - JSON响应: 包含错误信息的JSON对象。
            - HTTP状态码: 500 (Internal Server Error)
            - JSON响应: 包含错误信息的JSON对象。

    逻辑步骤:
        1. 获取表单数据。
        2. 查询指定实验室编号的实验室记录，如果记录不存在则返回404。
        3. 更新实验室记录中的相关字段。
        4. 提交更改到数据库。
        5. 构建包含更新后的实验室记录的JSON响应。
        6. 返回JSON响应。
    """
    try:
        # 获取表单数据
        data = request.form
        ico_path = data.get('ico_path')
        room_num = data.get('room_num')
        introduction = data.get('introduction')
        article = data.get('article')

        # 查询ssi_Lab表中的记录
        lab = ssi_Lab.query.filter_by(lab_number=lab_number, is_delete=False).first()
        if not lab:
            return get_response(StatusCodes.NOT_FOUND, message='Lab not found')

        # 更新记录
        if ico_path is not None:
            lab.ico_path = ico_path
        if room_num is not None:
            lab.room_num = room_num
        if introduction is not None:
            lab.introduction = introduction
        if article is not None:
            lab.article = article

        # 提交更改
        result = commit_session(db, StatusCodes.INTERNAL_SERVER_ERROR, 'Failed to update lab')
        if result:
            return result

        # 构建返回的JSON数据
        lab_data = item_to_dict(
            ssi_Lab, lab,
            additional_fields={
                'create_time': lambda lab: lab.create_time.isoformat(),
                'update_time': lambda lab: lab.update_time.isoformat() if lab.update_time else None
            }
        )

        return get_response(
            status=StatusCodes.OK,
            message='Lab updated successfully',
            data=lab_data
        )

    except Exception as e:
        app.logger.error(f"Error occurred: {e}")
        return get_response(StatusCodes.INTERNAL_SERVER_ERROR, message='Internal server error')

# 移动端 -> 上传/修改
@app.route('/mobile/lab/<int:lab_number>', methods=['GET'])
def get_ssi_lab(lab_number):
    """
    获取指定实验室编号的小屏实验室记录的详细信息。

    请求方法: GET
    请求路径: /mobile/lab/<int:lab_number>

    参数:
        - lab_number (int): 实验室编号。

    响应:
        - 成功:
            - HTTP状态码: 200
            - JSON响应: 包含实验室记录的详细信息的JSON对象。
        - 失败:
            - HTTP状态码: 404 (Not Found)
            - JSON响应: 包含错误信息的JSON对象。
            - HTTP状态码: 500 (Internal Server Error)
            - JSON响应: 包含错误信息的JSON对象。

    逻辑步骤:
        1. 查询指定实验室编号的实验室记录，如果记录不存在则返回404。
        2. 将 `ico_path` 转换为 base64 编码的字符串。
        3. 构建包含实验室记录详细信息的JSON响应。
        4. 返回JSON响应。
    """
    try:
        # 查询匹配的记录
        lab = ssi_Lab.query.filter_by(lab_number=lab_number, is_delete=False).first()
        if not lab:
            return get_response(StatusCodes.NOT_FOUND, message='Lab not found')

        # 将ico_path转为base64
        ico_base64 = image_to_base64(lab.ico_path) if lab.ico_path else None

        # 构建返回的JSON数据
        lab_data = item_to_dict(
            ssi_Lab, lab,
            additional_fields={
                'ico_path': lambda lab: ico_base64,
                'create_time': lambda lab: lab.create_time.isoformat() if lab.create_time else None,
                'update_time': lambda lab: lab.update_time.isoformat() if lab.update_time else None
            }
        )

        return get_response(
            status=StatusCodes.OK,
            data=lab_data
        )

    except Exception as e:
        app.logger.error(f"Error occurred: {e}")
        return get_response(StatusCodes.INTERNAL_SERVER_ERROR, message='Internal server error')

# --------------------- 另外的功能 --------------------- #
# 语音转文字
@app.route('/speech2text', methods=['POST'])
def speech2text():
    """
    将上传的音频文件转换为文本。

    请求方法: POST
    请求路径: /speech2text

    表单参数:
        - file (file): 音频文件。

    响应:
        - 成功:
            - HTTP状态码: 200
            - JSON响应: 包含识别结果的JSON对象。
        - 失败:
            - HTTP状态码: 400 (Bad Request)
            - JSON响应: 包含错误信息的JSON对象。
            - HTTP状态码: 500 (Internal Server Error)
            - JSON响应: 包含错误信息的JSON对象。

    逻辑步骤:
        1. 检查请求中是否包含音频文件。
        2. 读取音频文件并保存到临时文件。
        3. 调用ASR（自动语音识别）服务进行语音识别。
        4. 返回识别结果。
    """
    if 'file' not in request.files:
        raise CustomError('No file part in the request')

    file = request.files['file']
    if file.filename == '':
        raise CustomError('No selected file')

    if file:
        # 保存文件到内存
        audio_data = file.read()
        with tempfile.NamedTemporaryFile(delete=True) as temp_file:
            temp_file.write(audio_data)
            temp_file.flush()

            # 调用ASR进行语音识别
            try:
                result = asr_executor(audio_file=temp_file.name)
            except Exception as e:
                app.logger.error(f"ASR error: {e}")
                raise CustomError(str(e), status_code=500)

        # 返回识别结果
        return jsonify({'text': result})

# 文字转语音
@app.route('/text2speech', methods=['POST'])
def text2speech():
    """
    将提供的文本转换为语音文件并返回。

    请求方法: POST
    请求路径: /text2speech

    表单参数:
        - text (str): 需要转换为语音的文本。

    响应:
        - 成功:
            - HTTP状态码: 200
            - 文件响应: 包含生成的语音文件。
        - 失败:
            - HTTP状态码: 400 (Bad Request)
            - JSON响应: 包含错误信息的JSON对象。
            - HTTP状态码: 500 (Internal Server Error)
            - JSON响应: 包含错误信息的JSON对象。

    逻辑步骤:
        1. 检查请求中是否包含文本。
        2. 使用TTS（文本转语音）服务生成语音文件。
        3. 返回生成的语音文件。
    """
    if 'text' not in request.form:
        raise CustomError('No text provided')

    text = request.form['text']

    # 生成语音文件
    try:
        with BytesIO() as temp_file:
            tts_executor(text=text, output=temp_file)
            temp_file.seek(0)
            return send_file(temp_file, as_attachment=True, download_name='output.wav', mimetype='audio/wav')
    except Exception as e:
        app.logger.error(f"TTS error: {e}")
        raise CustomError(str(e), status_code=500)

# 错误处理器
@app.errorhandler(CustomError)
def handle_custom_error(error):
    """
    处理自定义错误并返回JSON响应。

    请求方法: 适用于所有HTTP方法
    请求路径: 适用于所有路径

    参数:
        - error (CustomError): 自定义错误对象。

    响应:
        - JSON响应: 包含错误信息的JSON对象。
        - HTTP状态码: 根据自定义错误对象的状态码。

    逻辑步骤:
        1. 创建包含错误信息的JSON响应。
        2. 设置响应的状态码。
        3. 返回JSON响应。
    """
    response = jsonify({'error': error.message})
    response.status_code = error.status_code
    return response

# 保存
@app.route('/save_guidance', methods=['POST'])
def save_guidance():
    """
        保存实验室指导信息。

        请求方法: POST
        请求路径: /save_guidance
        请求参数:
            - form:
                - lab_number (str): 实验室编号，必填。
                - points (str): 包含指导点信息的JSON字符串，必填。
            - files:
                - files (List[FileStorage]): 包含音频文件的列表，必填。

        响应:
            - 成功:
                - HTTP状态码: 200
                - JSON响应:
                    {
                        "state": 200,
                        "message": "Successfully Saved"
                    }
            - 失败:
                - HTTP状态码: 400 (Bad Request)
                - JSON响应:
                    {
                        "state": 400,
                        "message": "Missing form data" 或 "Points and files count mismatch" 或 "Invalid point data"
                    }
                - HTTP状态码: 500 (Internal Server Error)
                - JSON响应:
                    {
                        "state": 500,
                        "message": "Internal server error" 或 "Failed to save guidance"
                    }

        逻辑步骤:
            1. 检查请求中的表单数据是否完整。
            2. 解析 `points` 字段中的JSON数据。
            3. 检查 `points` 列表和上传的文件数量是否一致。
            4. 删除旧的指导记录。
            5. 插入新的指导记录，并保存上传的音频文件。
            6. 提交数据库更改。
        """
    try:
        # 检查表单数据
        missing, response = check_required_params(request.form, 'lab_number', 'points')
        if missing:
            return response

        lab_number = request.form['lab_number']
        points = request.form['points']
        files = request.files.getlist('files')

        # 解析points数据
        points_data = json.loads(points)

        # Step 1: 检查points和files的长度是否相等
        if len(points_data) != len(files):
            app.logger.error(f"Points and files count mismatch: points={len(points_data)}, files={len(files)}")
            return get_response(StatusCodes.BAD_REQUEST, message='Points and files count mismatch')

        # Step 2: 删除旧记录
        old_records = Guidance.query.filter_by(lab_number=lab_number, is_delete=0).all()
        for record in old_records:
            record.is_delete = 1
        db.session.commit()

        # Step 3: 插入新记录
        for index, point_data in enumerate(points_data):
            file = files[index]
            point_id = point_data.get('pointId')
            content = point_data.get('content')
            topic = point_data.get('topic')

            if not all([point_id, content, topic]):
                app.logger.error(f"Invalid point data: {point_data}")
                return get_response(StatusCodes.BAD_REQUEST, message='Invalid point data')

            # 生成安全的文件名
            filename = secure_filename(file.filename)
            audio_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            new_record = Guidance(
                lab_number=lab_number,
                point_id=point_id,
                content=content,
                topic=topic,
                audio_path=audio_path
            )
            db.session.add(new_record)
            file.save(audio_path)

        # 提交更改
        result = commit_session(db, StatusCodes.INTERNAL_SERVER_ERROR, 'Failed to save guidance')
        if result:
            return result

        return get_response(StatusCodes.OK, message='Successfully Saved')

    except Exception as e:
        app.logger.error(f"Error occurred: {e}")
        return get_response(StatusCodes.INTERNAL_SERVER_ERROR, message='Internal server error')

# 聊天机器人
history = [
    {
        "content": "请用一句话回答所有的问题。",
        "role": "user"
    },
    {
        "content": "好的，对于所有的问题我都会在一句话中回答清楚。",
        "role": "assistant"
    },
    {
        "content": "“和睦天盾”是中广核数科自主研发的国产实物保护集成管理平台，首台套机组应用于太平岭核电项目1号机组。",
        "role": "user"
    },
    {
        "content": "是的。",
        "role": "assistant"
    }
]

@app.route('/chat', methods=['POST'])
def chat():
    """
    处理聊天请求并生成模型的回复。

    请求方法: POST
    请求路径: /chat

    表单参数:
        - query (str): 用户输入的查询文本。

    响应:
        - 成功:
            - HTTP状态码: 200
            - JSON响应: 包含模型生成的回复的JSON对象。
        - 失败:
            - HTTP状态码: 400 (Bad Request)
            - JSON响应: 包含错误信息的JSON对象。
            - HTTP状态码: 500 (Internal Server Error)
            - JSON响应: 包含错误信息的JSON对象。

    逻辑步骤:
        1. 检查请求中是否包含 `query` 参数，如果没有则返回400错误。
        2. 记录生成回复的开始时间。
        3. 调用模型生成回复，并更新会话历史。
        4. 记录生成回复的结束时间，并计算耗时。
        5. 记录生成的回复和耗时信息。
        6. 返回模型生成的回复。
        7. 如果在处理过程中发生异常，记录错误信息并返回500错误。
    """
    try:
        # 检查请求中的query参数
        query = request.form.get('query')
        if not query:
            logger.error("No query provided.")
            return get_response(StatusCodes.BAD_REQUEST, message='No query provided.')

        # 记录开始时间
        start_time = time.time()

        # 生成回复
        response, updated_history = model.chat(
            tokenizer,
            query=query,
            history=history,
            temperature=app.config['TEMPERATURE'],
            top_p=app.config['TOP_P'],
            max_new_tokens=app.config['MAX_NEW_TOKENS']
        )

        # 记录结束时间
        end_time = time.time()
        elapsed_time = end_time - start_time
        logger.info(f"Response generated in {elapsed_time:.2f} seconds: {response}")

        # 更新会话历史
        history.extend(updated_history)

        # 返回模型的回复
        return get_response(StatusCodes.OK, data=response)

    except Exception as e:
        logger.error(f"Error occurred: {e}")
        return get_response(StatusCodes.INTERNAL_SERVER_ERROR, message='No query provided.')
