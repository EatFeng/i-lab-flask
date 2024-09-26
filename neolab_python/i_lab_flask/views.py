import time
from flask import request, redirect, url_for, jsonify
import os
from sqlalchemy.exc import IntegrityError
from i_lab_flask import app, db, tts_executor
from i_lab_flask.models import Lab, Guidance, ssi_Lab, Introductions
from datetime import  datetime


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
            content = request.form['content']
            audio_path = request.form['audio_path']

            new_guidance = Guidance(
                lab_id=lab.id,
                point_id=point_id,
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
                        'point_id': point_id,
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
        guidances = Guidance.query.filter_by(lab_id=lab.id).all()
        response = {
            'state': 200,
            'data_num': len(guidances),
            'data': [
                {'point_id': g.point_id, 'content': g.content, 'path': g.audio_path} for g in guidances
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
    ssi_labs = ssi_Lab.query.all()  # 获取数据库中的所有实验室信息
    ssi_labs_data = [
        {
            'id': lab.id,
            'lab_name': lab.lab_name,
            'location': lab.location,
            'create_time': lab.create_time,
            'update_time': lab.update_time,
            'is_delete': lab.is_delete,
            'lab_number': lab.lab_number
        }
        for ssi_lab in ssi_labs
    ]
    return jsonify({
        'state': 200,
        'data_num': len(ssi_labs),
        'data': ssi_labs_data
    })

# 新建
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
            create_time=datetime.utcnow(),
            update_time=datetime.utcnow()
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
                    'create_time': new_ssi_lab.create_time.isoformat(),
                    'update_time': new_ssi_lab.update_time.isoformat(),
                    'is_delete': new_ssi_lab.is_delete
                }
            })
        except IntegrityError:
            db.session.rollback()
            # 如果发生IntegrityError，返回错误信息
            return jsonify({'state': 400, 'message': 'Lab number already exists'}), 400
