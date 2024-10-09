from flask import request, jsonify, send_file
import os
from sqlalchemy.exc import IntegrityError
from i_lab_flask import app, db, tts_executor, asr_executor, tokenizer, model
from i_lab_flask.models import Lab, Guidance, ssi_Lab, Introductions
from datetime import  datetime
from zoneinfo import ZoneInfo
from werkzeug.utils import secure_filename
import tempfile
import json
from sqlalchemy import asc
import time
import base64

# 实验室管理页面
@app.route('/manage')
def manage():
    labs = Lab.query.all()  # 获取数据库中的所有实验室信息
    labs_data = [
        {
            'id': lab.id,
            'lab_name': lab.lab_name,
            'location': lab.location,
            'create_time': lab.create_time,
            'update_time': lab.update_time,
            'is_delete': lab.is_delete,
            'lab_number': lab.lab_number
        }
        for lab in labs
    ]
    return jsonify({
        'state': 200,
        'data_num': len(labs),
        'data': labs_data
    })

# 删除实验室
@app.route('/delete-lab/<int:lab_number>', methods=['POST'])
def delete_lab(lab_number):
    lab = Lab.query.filter_by(lab_number=lab_number).first()
    if lab:
        # 设置is_delete为1而不是删除记录
        lab.is_delete = True
        # 同时更新与该实验室ID关联的所有Guidance记录的is_delete字段
        related_guidances = Guidance.query.filter_by(lab_id=lab.id).all()
        for guidance in related_guidances:
            guidance.is_delete = True
        db.session.commit()
    else:
        # 如果实验室记录不存在，返回404状态码
        return jsonify({'state': 404, 'error_message': 'Lab not found'}), 404

    # 获取所有is_delete为False的实验室记录
    labs = Lab.query.filter_by(is_delete=False).all()
    labs_data = [
        {
            'id': lab.id,
            'lab_name': lab.lab_name,
            'location': lab.location,
            'create_time': lab.create_time,
            'update_time': lab.update_time,
            'is_delete': lab.is_delete,
            'lab_number': lab.lab_number
        }
        for lab in labs
    ]
    # 返回JSON响应
    return jsonify({
        'state': 200,
        'data_num': len(labs),
        'data': labs_data
    })

# 进入实验室页面
@app.route('/lab/<int:lab_number>', methods=['GET', 'POST'])
def lab(lab_number):
    lab = Lab.query.filter_by(lab_number=lab_number).first_or_404()
    if request.method == 'POST':
        if 'update_lab' in request.form:
            lab.lab_name = request.form['lab_name']
            lab.location = request.form['lab_location']
            try:
                db.session.commit()
                response = {
                    'state': 200,
                    'data_num': 1,
                    'data': {
                        'lab_number': lab.lab_number,
                        'lab_name': lab.lab_name,
                        'location': lab.location
                    }
                }
            except IntegrityError:
                db.session.rollback()
                response = {'state': 500, 'message': 'Integrity error'}
        elif 'add_guidance' in request.form:
            point_id = request.form['point_id']
            topic = request.form['topic']
            content = request.form['content']
            audio_path = request.form['audio_path']

            new_guidance = Guidance(
                lab_number=lab.lab_number,
                point_id=point_id,
                topic=topic,
                content=content,
                audio_path=audio_path
            )
            db.session.add(new_guidance)
            try:
                db.session.commit()
                response = {
                    'state': 200,
                    'data_num': 1,
                    'data': {
                        'lab_number': lab.lab_number,
                        'point_id': point_id,
                        'topic': topic,
                        'content': content,
                        'path': audio_path
                    }
                }
            except IntegrityError:
                db.session.rollback()
                response = {'state': 500, 'message': 'Integrity error'}
        elif 'update_guidance' in request.form:
            guidance_id = request.form['guidance_id']
            guidance = Guidance.query.get(guidance_id)
            if guidance:
                guidance.point_id = request.form['point_id']
                guidance.topic = request.form['topic']
                guidance.content = request.form['content']
                guidance.audio_path = request.form['audio_path']
                try:
                    db.session.commit()
                    response = {
                        'state': 200,
                        'data_num': 1,
                        'data': {
                            'guidance_id': guidance.id,
                            'point_id': guidance.point_id,
                            'topic': guidance.topic,
                            'content': guidance.content,
                            'path': guidance.audio_path
                        }
                    }
                except IntegrityError:
                    db.session.rollback()
                    response = {'state': 500, 'message': 'Integrity error'}
            else:
                response = {'state': 404, 'message': 'Guidance not found'}
        return jsonify(response)
    else:
        guidances = Guidance.query.filter_by(lab_number=lab_number, is_delete=False).order_by(asc(Guidance.point_id)).all()
        response = {
            'state': 200,
            'data_num': len(guidances),
            'data': [
                {'point_id': g.point_id,
                 'topic': g.topic,
                 'content': g.content,
                 'path': g.audio_path
                 } for g in guidances
            ],
            'lab_number': lab.lab_number
        }
        return jsonify(response)

# 新建实验室页面
@app.route('/new_lab', methods=['POST'])
def new_lab():
    if request.method == 'POST':
        lab_name = request.form['lab_name']
        lab_location = request.form['lab_location']
        lab_number = request.form['lab_number']
        new_lab = Lab(lab_name=lab_name, location=lab_location, lab_number=lab_number)
        try:
            db.session.add(new_lab)
            db.session.commit()
            # 创建成功后，返回新实验室的信息
            return jsonify({
                'state': 200,
                'data': {
                    'id': new_lab.id,
                    'lab_name': new_lab.lab_name,
                    'location': new_lab.location,
                    'lab_number': new_lab.lab_number
                }
            })
        except IntegrityError:
            db.session.rollback()
            # 如果发生IntegrityError，返回错误信息
            return jsonify({'state': 400, 'message': 'Lab number already exists'}), 400

# 生成语音请求
@app.route('/lab/generate-audio/<int:guidance_id>', methods=['POST'])
def generate_audio(guidance_id):
    guidance = Guidance.query.get(guidance_id)
    if guidance:
        # 删除旧的音频文件
        if guidance.audio_path is not None and guidance.audio_path[-3:] == 'wav':
            os.remove(guidance.audio_path)
        # 生成音频
        timestamp = int(time.time())  # 获取当前时间戳
        audio_file_name = f'{guidance_id}_{timestamp}.wav'
        audio_file_path = 'i_lab_flask/output/' + audio_file_name
        tts_executor(text=guidance.content, output=audio_file_path)
        # 更新数据库
        guidance.audio_path = audio_file_path
        db.session.commit()
        # 返回JSON响应
        return jsonify({
            'state': 200,
            'data': {
                'guidance_id': guidance.id,
                'lab_number': guidance.lab_number,
                'point_id': guidance.point_id,
                'content': guidance.content,
                'audio_path': guidance.audio_path
            }
        })
    else:
        # 如果guidance记录不存在，返回404状态码
        return jsonify({'state': 404, 'error_message': 'Guidance not found'}), 404

# 获取音频文件
@app.route('/get_audio', methods=['POST'])
def get_audio():
    point_id = request.form.get('point_id')
    lab_number = request.form.get('lab_number')

    if point_id is None or lab_number is None:
        return jsonify({'error': 'Missing point_id or lab_number',
                        'state':400
                        }), 400

    # 在Guidance模型中检索匹配的记录
    guidance = Guidance.query.filter_by(point_id=point_id, lab_number=lab_number, is_delete=False).first()
    if guidance is None:
        return jsonify({'error': 'Guidance Record not found',
                        'state': 404
                        }), 404

    # 检查数据库中是否保存该记录的音频路径
    if guidance.audio_path is None:
        return jsonify({'error': 'The audio has not been generated yet',
                        'state': 404
                        }), 404

    # 确保文件存在
    audio_file_path = os.path.join(app.config['UPLOAD_FOLDER'], guidance.audio_path)
    print(audio_file_path)
    if not os.path.isfile(audio_file_path):
        return jsonify({'error': 'Audio file not found',
                        'state': 404
                        }), 404

    # 返回音频文件
    return send_file(audio_file_path, as_attachment=True, download_name=secure_filename(guidance.audio_path))

# 上传音频文件
@app.route('/upload_audio', methods=['POST'])
def upload_audio():
    # 检查是否有文件在请求中
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request',
                        'state': 400
                        }), 400

    file = request.files['file']
    point_id = request.form.get('point_id')
    lab_number = request.form.get('lab_number')

    if file.filename == '':
        return jsonify({'error': 'No selected file',
                        'state': 400
                        }), 400
    if point_id is None or lab_number is None:
        return jsonify({'error': 'Missing point_id or lab_number',
                        'state': 400
                        }), 400

    if file and allowed_audio_file(file.filename):
        filename = 'i_lab_flask/upload/' + secure_filename(file.filename)
        audio_file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(audio_file_path)

        # 查找匹配的记录并更新is_delete
        existing_guidance = Guidance.query.filter_by(point_id=point_id, lab_number=lab_number, is_delete=False).first()
        if existing_guidance:
            existing_guidance.is_delete = True
            content = existing_guidance.content
            topic = existing_guidance.topic
            db.session.commit()
        else:
            return jsonify({'error': 'Guidance Record not found',
                            'state': 404
                            }), 404

        # 保存记录到数据库
        new_guidance = Guidance(point_id=point_id,
                                lab_number=lab_number,
                                topic = topic,
                                content = content,
                                audio_path=filename)
        db.session.add(new_guidance)
        db.session.commit()

        return jsonify({'message': 'File uploaded successfully',
                        'path': audio_file_path,
                        'state': 200
                        }), 200

    else:
        return jsonify({'error': 'File type not allowed',
                        'state': 400
                        }), 400

# 发送讲解内容
@app.route('/get_guidance_content', methods=['POST'])
def get_guidance_content():
    point_id = request.form.get('point_id')
    lab_number = request.form.get('lab_number')

    if point_id is None or lab_number is None:
        return jsonify({'error': 'Missing point_id or lab_number',
                        'state:': 400
                        }), 400

    # 在Guidance模型中检索匹配的记录
    guidance = Guidance.query.filter_by(point_id=point_id, lab_number=lab_number).first()

    # 检查是否找到记录
    if guidance is None:
        return jsonify({'error': 'Guidance not found',
                        'state': 404
                        }), 404

    # 检查content字段是否为null或者非null但是内容为空
    if guidance.content is None or (guidance.content is not None and not guidance.content.strip()):
        return jsonify({'error': 'Content is empty or null',
                        'state': 404
                        }), 404

    # 返回content字段数据的JSON
    response = {
        'point_id': guidance.point_id,
        'lab_number': guidance.lab_number,
        'content': guidance.content
    }
    return jsonify(response)

# 删除讲解请求
@app.route('/lab/<int:lab_number>/delete-guidance/<int:guidance_id>', methods=['POST'])
def delete_guidance(lab_number, guidance_id):
    guidance = Guidance.query.get(guidance_id)
    if guidance:
        # 设置is_delete为1而不是删除记录
        guidance.is_delete = 1
        db.session.commit()
        # 查询所有is_delete为False的guidance记录
        guidances = Guidance.query.filter_by(lab_number=lab_number, is_delete=False).all()
        # 准备返回的JSON数据
        response_data = [
            {'guidance_id': g.id,
             'lab_number': g.lab_number,
             'point_id': g.point_id,
             'content': g.content,
             'path': g.audio_path}
            for g in guidances
        ]
        # 返回JSON响应
        return jsonify({
            'state': 200,
            'data_num': len(response_data),
            'data': response_data
        })
    else:
        # 如果guidance记录不存在，返回404状态码
        return jsonify({'state': 404, 'message': 'Guidance not found'}), 404

# --------------------- 小屏介绍管理页 --------------------- #
# 小屏介绍页面
@app.route('/ssi/manage')
def ssi_manage():
    ssi_labs = ssi_Lab.query.filter_by(is_delete=False).all()
    ssi_labs_data = [
        {
            'id': ssi_lab.id,
            'lab_name': ssi_lab.lab_name,
            'location': ssi_lab.location,
            'create_time': ssi_lab.create_time.strftime('%Y-%m-%d %H:%M:%S') if ssi_lab.create_time else None,
            'update_time': ssi_lab.update_time.strftime('%Y-%m-%d %H:%M:%S') if ssi_lab.update_time else None,
            'is_delete': ssi_lab.is_delete,
            'lab_number': ssi_lab.lab_number,
            'img_segmentation': ssi_lab.img_segmentation,
            'img_total': ssi_lab.img_total
        }
        for ssi_lab in ssi_labs
    ]
    return jsonify({
        'state': 200,
        'data_num': len(ssi_labs),
        'data': ssi_labs_data
    })

# 小屏讲解管理页 -> 新建
@app.route('/ssi/new_lab', methods=['POST'])
def ssi_new_lab():
    if request.method == 'POST':
        lab_name = request.form['lab_name']
        lab_location = request.form['lab_location']
        lab_number = request.form['lab_number']

        new_ssi_lab = ssi_Lab(
            lab_name=lab_name,
            location=lab_location,
            lab_number=lab_number,
            create_time=beijing_time_now(),
            update_time=beijing_time_now()
        )
        try:
            db.session.add(new_ssi_lab)
            db.session.commit()
            # 创建成功后，返回新实验室的信息
            return jsonify({
                'state': 200,
                'data': {
                    'id': new_ssi_lab.id,
                    'lab_name': new_ssi_lab.lab_name,
                    'location': new_ssi_lab.location,
                    'create_time': new_ssi_lab.create_time.strftime('%Y-%m-%d %H:%M:%S') if ssi_lab.create_time else None,
                    'update_time': new_ssi_lab.update_time.strftime('%Y-%m-%d %H:%M:%S') if ssi_lab.update_time else None,
                    'is_delete': new_ssi_lab.is_delete,
                    'lab_number': new_ssi_lab.lab_number,
                    'img_segmentation': new_ssi_lab.img_segmentation,
                    'img_total': new_ssi_lab.img_total
                }
            })
        except IntegrityError:
            db.session.rollback()
            # 如果发生IntegrityError，返回错误信息
            return jsonify({'state': 400, 'message': 'Lab number already exists'}), 400

# 小屏讲解管理页 -> 删除
@app.route('/ssi/delete_lab/<int:lab_number>', methods=['POST'])
def ssi_delete_lab(lab_number):
    ssi_lab = ssi_Lab.query.filter_by(lab_number=lab_number).first()
    if ssi_lab:
        # 设置is_delete为1而不是删除记录
        ssi_lab.is_delete = True
        ssi_lab.update_time = beijing_time_now()
        # 同时更新与该实验室ID关联的所有Guidance记录的is_delete字段
        related_intros = Introductions.query.filter_by(lab_number=ssi_Lab.lab_number).all()
        for intro in related_intros:
            intro.is_delete = True
        db.session.commit()
    else:
        # 如果实验室记录不存在，返回404状态码
        return jsonify({'state': 404, 'error_message': 'Lab not found'}), 404

    # 获取所有is_delete为False的实验室记录
    ssi_labs = ssi_Lab.query.filter_by(is_delete=False).all()
    labs_data = [
        {
            'id': ssi_lab.id,
            'lab_name': ssi_lab.lab_name,
            'location': ssi_lab.location,
            'create_time': ssi_lab.create_time.strftime('%Y-%m-%d %H:%M:%S') if ssi_lab.create_time else None,
            'update_time': ssi_lab.update_time.strftime('%Y-%m-%d %H:%M:%S') if ssi_lab.update_time else None,
            'is_delete': ssi_lab.is_delete,
            'lab_number': ssi_lab.lab_number,
            'img_segmentation': ssi_lab.img_segmentation,
            'img_total': ssi_lab.img_total
        }
        for ssi_lab in ssi_labs
    ]
    # 返回JSON响应
    return jsonify({
        'state': 200,
        'data_num': len(ssi_labs),
        'data': labs_data
    })

# 小屏讲解管理页 -> 编辑
@app.route('/ssi/update_lab/<int:lab_number>', methods=['POST'])
def ssi_update_lab(lab_number):
    # 从表单中获取数据
    form = request.form
    if 'update_lab' in form:
        lab_name = form.get('lab_name')
        lab_location = form.get('lab_location')

        # 根据实验室编号查找实验室
        lab = ssi_Lab.query.filter_by(lab_number=lab_number).first()
        if lab:
            # 更新实验室信息
            lab.lab_name = lab_name
            lab.location = lab_location
            lab.update_time = beijing_time_now()
            db.session.commit()

            # 返回更新后的实验室信息
            return jsonify({
                'state': 200,
                'message': 'Lab updated successfully',
                'data': {
                    'id': lab.id,
                    'lab_name': lab.lab_name,
                    'location': lab.location,
                    'create_time': lab.create_time.strftime('%Y-%m-%d %H:%M:%S') if ssi_lab.create_time else None,
                    'update_time': lab.update_time.strftime('%Y-%m-%d %H:%M:%S') if ssi_lab.update_time else None,
                    'is_delete': lab.is_delete,
                    'lab_number': lab.lab_number,
                    'img_segmentation': lab.img_segmentation,
                    'img_total': lab.img_total
                }
            })
        else:
            # 如果找不到实验室记录，返回404状态码
            return jsonify({'state': 404, 'message': 'Lab not found'}), 404
    else:
        # 如果表单中没有update_lab字段或者值不是'true'，返回400状态码
        return jsonify({'state': 400, 'message': 'Invalid request...'}), 400

# 小屏讲解管理页 -> 详情
@app.route('/ssi/lab/<int:lab_number>', methods=['GET'])
def ssi_lab(lab_number):
    if lab_number is None:
        return jsonify({'error': 'Missing lab_number parameter', 'state': 400}), 400

    try:
        # 查询ssi_Lab表中的记录
        lab = ssi_Lab.query.filter_by(lab_number=lab_number, is_delete=False).first()
        if not lab:
            return jsonify({'error': 'Lab not found', 'state': 404}), 404

        # 将ssi_lab中的img_segmentation和img_total转为base64，传回前端
        img_seg_base64 = photo2base64(lab.img_segmentation)
        img_tot_base64 = photo2base64(lab.img_total)

        # 查询Introductions表中的记录
        intros = Introductions.query.filter_by(lab_number=lab_number, is_delete=False).all()
        if not intros:
            return jsonify({'error': 'introduction not found', 'state': 404}), 404

        lab_data = {
            'id': lab.id,
            'lab_name': lab.lab_name,
            'location': lab.location,
            'create_time': lab.create_time.isoformat(),
            'update_time': lab.update_time.isoformat(),
            'is_delete': lab.is_delete,
            'lab_number': lab.lab_number,
            'img_segmentation': img_seg_base64,
            'img_total': img_tot_base64,
            'ico_path': lab.ico_path,
            'room_num': lab.room_num,
            'introduction': lab.introduction,
            'article': lab.article
        }

        intros_data = [
            {
                'id': intro.id,
                'lab_number': intro.lab_number,
                'image_path': intro.image_path if intro.image_path else None,
                'summary': intro.summary,
                'details': intro.details,
                'is_delete': intro.is_delete,
                'update_time': intro.update_time.isoformat() if intro.update_time else None,
                'point_id': intro.point_id,
                'x': intro.x,
                'y': intro.y
            }
            for intro in intros
        ]

        return jsonify({'state': 200 ,'lab': lab_data, 'data': intros_data}), 200

    except Exception as e:
        app.logger.error(f"Error occurred: {e}")
        return jsonify({'error': 'Internal server error', 'state': 500}), 500

# 小屏讲解管理页 -> 详情 -> 新建
@app.route('/ssi/add_intro/<int:lab_number>', methods=['POST'])
def add_intro(lab_number):
    # 从表单中获取数据
    summary = request.form.get('summary')
    details = request.form.get('details')

    if not summary or not details:
        return jsonify({'error': 'Missing summary or details', 'state': 400}), 400

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
    try:
        db.session.add(new_intro)
        db.session.commit()
        return jsonify({
            'state': 200,
            'data': {
                'id': new_intro.id,
                'lab_number': new_intro.lab_number,
                'time_line': new_intro.time_line.isoformat(),
                'summary': new_intro.summary,
                'details': new_intro.details,
                'is_delete': new_intro.is_delete,
                'update_time': new_intro.update_time.isoformat() if new_intro.update_time else None,
                'point_id': new_intro.point_id,
                'x': new_intro.x,
                'y': new_intro.y
            }
        }), 200
    except Exception as e:
        app.logger.error(f"Error occurred: {e}")
        return jsonify({'error': 'Internal server error', 'state': 500}), 500

# 小屏讲解管理页 -> 详情 -> 编辑
@app.route('/ssi/update_intro/<int:point_id>', methods=['POST'])
def update_intro(point_id):
    # 从表单中获取数据
    summary = request.form.get('summary')
    details = request.form.get('details')

    if not summary or not details:
        return jsonify({'error': 'Missing summary or details', 'state': 400}), 400

    # 获取当前时间
    current_time = beijing_time_now()

    # 查询匹配的记录
    intro = Introductions.query.filter_by(id=point_id).first()
    if intro is None:
        return jsonify({'error': 'Introduction not found', 'state': 404}), 404

    # 更新记录
    try:
        intro.summary = summary
        intro.details = details
        intro.update_time = current_time
        db.session.commit()

        # 返回更新后的记录
        return jsonify({
            'state': 200,
            'data': {
                'id': intro.id,
                'lab_number': intro.lab_number,
                'time_line': intro.time_line.isoformat(),
                'summary': intro.summary,
                'details': intro.details,
                'is_delete': intro.is_delete,
                'update_time': intro.update_time.isoformat() if intro.update_time else None,
                'point_id': intro.point_id,
                'x': intro.x,
                'y': intro.y
            }
        }), 200

    except Exception as e:
        app.logger.error(f"Error occurred: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error', 'state': 500}), 500

# 小屏讲解管理页 -> 详情 -> 删除
@app.route('/ssi/delete_intro/<int:point_id>/<int:lab_number>', methods=['POST'])
def delete_intro(point_id, lab_number):
    # 查询匹配的记录
    intro = Introductions.query.filter_by(id=point_id, lab_number=lab_number, is_delete=False).first()
    if intro is None:
        return jsonify({'error': 'Introduction not found or already deleted', 'state': 404}), 404

    # 更新is_delete字段
    intro.is_delete = True
    try:
        db.session.commit()
    except Exception as e:
        app.logger.error(f"Error occurred: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error', 'state': 500}), 500

    # 查询lab_number匹配且is_delete为False的所有记录
    intros = Introductions.query.filter_by(lab_number=lab_number, is_delete=False).all()

    # 构建返回的数据
    intros_data = [
        {
            'id': record.id,
            'lab_number': record.lab_number,
            'time_line': record.time_line.isoformat(),
            'summary': record.summary,
            'details': record.details,
            'is_delete': record.is_delete,
            'update_time': record.update_time.isoformat() if record.update_time else None,
            'point_id': record.point_id,
            'x': record.x,
            'y': record.y
        }
        for record in intros
    ]

    # 返回查询结果
    return jsonify(intros_data), 200

# 小屏讲解管理页 -> 详情 -> 获取照片
@app.route('/ssi/get_image/<int:lab_number>/<int:point_id>', methods=['GET'])
def get_image(lab_number, point_id):
    # 查询匹配的记录
    intro = Introductions.query.filter_by(lab_number=lab_number, point_id=point_id, is_delete=False).first()
    if intro is None or not intro.image_path:
        return jsonify({'error': 'Image not found', 'state': 404}), 404

    # 构建图片文件的路径
    image_file_path = os.path.join(app.config['UPLOAD_FOLDER'], intro.image_path)
    print(image_file_path)
    # 检查图片文件是否存在
    if not os.path.isfile(image_file_path):
        return jsonify({'error': 'Image file not found', 'state': 404}), 404

    # 返回图片文件
    return send_file(image_file_path, mimetype='image/png')


# 小屏讲解管理页 -> 详情 -> 上传照片
@app.route('/ssi/upload_image/<int:lab_number>/<int:point_id>', methods=['POST'])
def upload_image(lab_number, point_id):
    # 检查是否有文件在请求中
    if 'image' not in request.files:
        return jsonify({'error': 'No image part in the request', 'state': 400}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No selected file', 'state': 400}), 400

    if file and allowed_image_file(file.filename):
        filename = 'i_lab_flask/images/' + secure_filename(file.filename)
        image_file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(image_file_path)

        # 查询匹配的记录
        intro = Introductions.query.filter_by(lab_number=lab_number, point_id=point_id, is_delete=False).first()
        if intro is None:
            return jsonify({'error': 'Introduction not found', 'state': 404}), 404

        # 更新image_path字段
        intro.image_path = image_file_path
        try:
            db.session.commit()
            return jsonify(
                {'message': 'Image uploaded and path updated successfully', 'state': 200, 'path': image_file_path}), 200
        except Exception as e:
            app.logger.error(f"Error occurred: {e}")
            db.session.rollback()
            return jsonify({'error': 'Internal server error', 'state': 500}), 500
    else:
        return jsonify({'error': 'File type not allowed', 'state': 400}), 400

# 移动端 -> 上传/修改
@app.route('/mobile/edit_lab/<int:lab_number>', methods=['POST'])
def update_ssi_lab(lab_number):
    # 获取表单数据
    data = request.form
    ico_path = data.get('ico_path')
    room_num = data.get('room_num')
    introduction = data.get('introduction')
    article = data.get('article')

    # 查询ssi_Lab表中的记录
    lab = ssi_Lab.query.filter_by(lab_number=lab_number, is_delete=False).first()
    if not lab:
        return jsonify({'error': 'Lab not found', 'state': 404}), 404

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
    db.session.commit()

    # 构建返回的JSON数据
    lab_data = {
        'id': lab.id,
        'lab_name': lab.lab_name,
        'location': lab.location,
        'create_time': lab.create_time.isoformat(),
        'update_time': lab.update_time.isoformat(),
        'is_delete': lab.is_delete,
        'lab_number': lab.lab_number,
        'img_segmentation': lab.img_segmentation,
        'img_total': lab.img_total,
        'ico_path': lab.ico_path,
        'room_num': lab.room_num,
        'introduction': lab.introduction,
        'article': lab.article
    }

    return jsonify({'state': 200, 'message': 'Lab updated successfully', 'data': lab_data}), 200

@app.route('/mobile/lab/<int:lab_number>', methods=['GET'])
def get_ssi_lab(lab_number):
    # 查询ssi_Lab表中的记录
    lab = ssi_Lab.query.filter_by(lab_number=lab_number, is_delete=False).first()
    if not lab:
        return jsonify({'error': 'Lab not found', 'state': 404}), 404

    ico_base64 = photo2base64(lab.ico_path)

    # 构建返回的JSON数据
    lab_data = {
        'id': lab.id,
        'lab_number': lab.lab_number,
        'lab_name': lab.lab_name,
        'ico_path': ico_base64,
        'room_num': lab.room_num,
        'introduction': lab.introduction,
        'article': lab.article
    }

    return jsonify({'state': 200, 'data': lab_data}), 200

# --------------------- 另外的功能 --------------------- #
# 语音转文字
@app.route('/speech2text', methods=['POST'])
def speech2text():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file:
        filename = 'temp.wav'
        file.save(filename)

        # 调用ASR进行语音识别
        try:
            result = asr_executor(audio_file=filename)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

        # 删除临时文件
        os.remove(filename)

        # 返回识别结果
        return jsonify({'text': result})

# 文字转语音
@app.route('/text2speech', methods=['POST'])
def text2speech():
    if 'text' not in request.form:
        return jsonify({'error': 'No text provided'}), 400

    text = request.form['text']
    # 创建临时文件
    temp_dir = tempfile.gettempdir()
    temp_file = os.path.join(temp_dir, 'output.wav')

    # 生成语音文件
    tts_executor(text=text, output=temp_file)

    # 发送语音文件
    return send_file(temp_file, as_attachment=True)

# 保存
@app.route('/save_guidance', methods=['POST'])
def save_guidance():
    # 检查表单数据
    if 'lab_number' not in request.form or 'points' not in request.form or 'files' not in request.files:
        return jsonify({'error': 'Missing form data'}), 400

    lab_number = request.form['lab_number']
    points = request.form['points']
    files = request.files.getlist('files')

    # 解析points数据
    points_data = json.loads(points)

    # Step 1: 检查points和files的长度是否相等
    if len(points_data) != len(files):
        print(points_data)
        print(len(points_data))
        print(files, len(files))
        return jsonify({'error': 'Points and files count mismatch'}), 400

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

        new_record = Guidance(
            lab_number=lab_number,
            point_id=point_id,
            content=content,
            topic=topic,
            audio_path='i_lab_flask/output/' + secure_filename(file.filename)
        )
        db.session.add(new_record)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], new_record.audio_path))
    db.session.commit()

    return jsonify({'message': 'Successfully Saved'})

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
    global history
    query = request.form.get('query')
    print(query)
    if not query:
        return jsonify({'error': 'No query provided.'}), 400

    start_time = time.time()
    # 生成回复
    response, history = model.chat(tokenizer, query=query, history=history, temperature=0.3, top_p=0.8, max_new_tokens=64)
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(response, elapsed_time)

    # 返回模型的回复和语音文件路径
    return jsonify({'response': response})

# 获取当前时间的北京时间
def beijing_time_now():
     return datetime.now(ZoneInfo("Asia/Shanghai"))

# 允许的音频文件格式
def allowed_audio_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in {'wav'}

# 允许的图片文件格式
def allowed_image_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

# 将图片转为base64
def photo2base64(image_path):
    encoded_string = ''
    # 检查图片是否存在
    if image_path is not None:
        if not os.path.exists(image_path):
            return "Image not found", 404
        else:
            # 读取图片文件并转换为base64字符串
            with open(image_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')

    return encoded_string
