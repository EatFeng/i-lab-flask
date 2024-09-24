import time
from flask import render_template, request, redirect, url_for
import os
from sqlalchemy.exc import IntegrityError
from i_lab_flask import app, db, tts_executor
from i_lab_flask.models import Lab, Guidance

# home页
@app.route('/home')
def home():
    return render_template('home.html')

# 实验室管理页面
@app.route('/manage')
def manage():
    labs = Lab.query.all()  # 获取数据库中的所有实验室信息
    return render_template('manage.html', labs=labs)

# 删除实验室
@app.route('/delete-lab/<int:lab_id>', methods=['POST'])
def delete_lab(lab_id):
    lab = Lab.query.get(lab_id)
    if lab:
        # 删除与此实验室相关的所有Guidance记录
        related_guidances = Guidance.query.filter_by(lab_id=lab_id).all()
        for guidance in related_guidances:
            file_path = './static' + guidance.audio_path[1:]
            if os.path.exists(file_path) and file_path[-3:] == 'wav':
                os.remove(file_path)
            db.session.delete(guidance)
        db.session.commit()

        # 删除实验室记录
        db.session.delete(lab)
        db.session.commit()
    return redirect(url_for('manage'))

# 进入实验室页面
@app.route('/lab/<int:lab_id>', methods=['GET', 'POST'])
def lab(lab_id):
    lab = Lab.query.get_or_404(lab_id)
    if request.method == 'POST':
        if 'update_lab' in request.form:
            lab.name = request.form['lab_name']
            lab.location = request.form['lab_location']
            lab.department = request.form['lab_department']
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
        elif 'add_guidance' in request.form:
            lab_id = lab.id
            point_id = request.form['point_id']
            content = request.form['content'],
            audio_path = request.form['audio_path']

            new_guidance = Guidance(
                lab_id=lab_id,
                point_id=point_id,
                content=content,
                audio_path=audio_path
            )
            db.session.add(new_guidance)
            db.session.commit()
        elif 'update_guidance' in request.form:
            guidance_id = request.form['guidance_id']
            guidance = Guidance.query.get(guidance_id)
            if guidance:
                guidance.point_id = request.form['point_id']
                guidance.content = request.form['content']
                guidance.audio_path = request.form['audio_path']
                try:
                    db.session.commit()
                except IntegrityError:
                    db.session.rollback()
        return redirect(url_for('lab', lab_id=lab.id))
    else:
        guidances = Guidance.query.filter_by(lab_id=lab_id).all()
        return render_template('lab.html', lab=lab, guidances=guidances)

# 新建实验室页面
@app.route('/new-lab', methods=['GET', 'POST'])
def new_lab():
    if request.method == 'POST':
        lab_name = request.form['lab_name']
        lab_location = request.form['lab_location']
        lab_department = request.form['lab_department']
        new_lab = Lab(name=lab_name, location=lab_location, department=lab_department)
        try:
            db.session.add(new_lab)
            db.session.commit()
            return redirect(url_for('manage'))
        except IntegrityError:
            db.session.rollback()
    return render_template('new_lab.html')

# 生成语音请求
@app.route('/lab/<int:lab_id>/generate-audio/<int:guidance_id>', methods=['POST'])
def generate_audio(lab_id, guidance_id):
    guidance = Guidance.query.get(guidance_id)
    if guidance:
        # 删除旧的音频文件
        file_path = './static' + guidance.audio_path[1:]
        if os.path.exists(file_path) and file_path[-3:] == 'wav':
            os.remove(file_path)
        # 生成音频
        timestamp = int(time.time())  # 获取当前时间戳
        audio_file_name = f'{guidance_id}_{timestamp}.wav'
        audio_file_path = './output/' + audio_file_name
        audio_file_output_path = './static/output/' + audio_file_name
        tts_executor(text=guidance.content, output=audio_file_output_path)
        # 更新数据库
        guidance.audio_path = audio_file_path
        db.session.commit()
    return redirect(url_for('lab', lab_id=lab_id))

# 删除讲解请求
@app.route('/lab/<int:lab_id>/delete-guidance/<int:guidance_id>', methods=['POST'])
def delete_guidance(lab_id, guidance_id):
    guidance = Guidance.query.get(guidance_id)
    if guidance:
        # 删除音频文件
        file_path = './static' + guidance.audio_path[1:]
        if os.path.exists(file_path) and file_path[-3:] == 'wav':
            os.remove(file_path)
        # 删除数据库记录
        db.session.delete(guidance)
        db.session.commit()
    return redirect(url_for('lab', lab_id=lab_id))

@app.before_first_request
def create_tables():
    db.create_all()