from i_lab_flask import db

class Lab(db.Model):
    __tablename__ = 'labs'
    id = db.Column(db.BigInteger, primary_key=True)
    lab_name = db.Column(db.String(80), unique=True, nullable=False)
    location = db.Column(db.String(255), nullable=True)
    create_time = db.Column(db.DateTime, nullable=True)
    update_time = db.Column(db.DateTime, nullable=True)
    is_delete = db.Column(db.Boolean, nullable=False, default=False)
    lab_number = db.Column(db.Integer, nullable=False, unique=True)

class Guidance(db.Model):
    __tablename__ = 'guidance'
    id = db.Column(db.Integer, primary_key=True)
    lab_id = db.Column(db.BigInteger, db.ForeignKey('labs.id'), nullable=False)
    point_id = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=False)
    audio_path = db.Column(db.String(120), nullable=True)
    is_delete = db.Column(db.Boolean, nullable=False, default=False)