import time
from flask import request, redirect, url_for, jsonify, send_file
import os
from sqlalchemy.exc import IntegrityError
from i_lab_flask import app, db, tts_executor
from i_lab_flask.models import Lab, Guidance, ssi_Lab, Introductions
from datetime import  datetime
from zoneinfo import ZoneInfo
from werkzeug.utils import secure_filename


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
        guidances = Guidance.query.filter_by(lab_number=lab.id).all()
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
            file_path = './i_lab_flask/static' + guidance.audio_path[1:]
            os.remove(file_path)
        # 生成音频
        timestamp = int(time.time())  # 获取当前时间戳
        audio_file_name = f'{guidance_id}_{timestamp}.wav'
        audio_file_path = './output/' + audio_file_name
        audio_file_output_path = './i_lab_flask/static/output/' + audio_file_name
        tts_executor(text=guidance.content, output=audio_file_output_path)
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

# 获取语音文件
@app.route('/get_audio', methods=['POST'])
def get_audio():
    point_id = request.form.get('point_id')
    lab_number = request.form.get('lab_number')

    if point_id is None or lab_number is None:
        return jsonify({'error': 'Missing point_id or lab_number',
                        'state':400
                        }), 400

    # 在Guidance模型中检索匹配的记录
    guidance = Guidance.query.filter_by(point_id=point_id, lab_number=lab_number).first()
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

# 获取讲解内容
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
            'lab_number': ssi_lab.lab_number
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
                    'lab_number': new_ssi_lab.lab_number,
                    'create_time': new_ssi_lab.create_time.strftime('%Y-%m-%d %H:%M:%S') if new_ssi_lab.create_time else None,
                    'update_time': new_ssi_lab.update_time.strftime('%Y-%m-%d %H:%M:%S') if new_ssi_lab.update_time else None,
                    'is_delete': new_ssi_lab.is_delete
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
            'lab_number': ssi_lab.lab_number
        }
        for ssi_lab in ssi_labs
    ]
    # 返回JSON响应
    return jsonify({
        'state': 200,
        'data_num': len(ssi_labs),
        'data': labs_data
    })

# 小屏讲解管理页 -> 删除
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
                    'create_time': lab.create_time.strftime('%Y-%m-%d %H:%M:%S') if lab.create_time else None,
                    'update_time': lab.update_time.strftime('%Y-%m-%d %H:%M:%S') if lab.update_time else None,
                    'is_delete': lab.is_delete,
                    'lab_number': lab.lab_number
                }
            })
        else:
            # 如果找不到实验室记录，返回404状态码
            return jsonify({'state': 404, 'message': 'Lab not found'}), 404
    else:
        # 如果表单中没有update_lab字段或者值不是'true'，返回400状态码
        return jsonify({'state': 400, 'message': 'Invalid request...'}), 400

# 获取当前时间的北京时间
def beijing_time_now():
     return datetime.now(ZoneInfo("Asia/Shanghai"))
