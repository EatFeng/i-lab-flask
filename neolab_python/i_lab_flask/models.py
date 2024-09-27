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
    lab_number = db.Column(db.Integer, db.ForeignKey('labs.lab_number'), nullable=False)
    point_id = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=False)
    audio_path = db.Column(db.String(255), nullable=True)
    is_delete = db.Column(db.Integer, default=0, nullable=False)
    topic=db.Column(db.String(255), nullable=False)

class ssi_Lab(db.Model):
    __tablename__ = 'ssi_labs'
    id = db.Column(db.BigInteger, primary_key=True)
    lab_name = db.Column(db.String(80), unique=True, nullable=False)
    location = db.Column(db.String(255), nullable=True)
    create_time = db.Column(db.DateTime, nullable=False)
    update_time = db.Column(db.DateTime, nullable=False)
    is_delete = db.Column(db.Boolean, nullable=False, default=False)
    lab_number = db.Column(db.Integer, nullable=False, unique=True)

class Introductions(db.Model):
    __tablename__ = 'intro'
    id = db.Column(db.Integer, primary_key=True)
    lab_number = db.Column(db.Integer, db.ForeignKey('labs.lab_number'), nullable=False)
    time_line = db.Column(db.DateTime, nullable=False)
    summary= db.Column(db.String(200), nullable=False)
    details = db.Column(db.Text, nullable=False)
    is_delete = db.Column(db.Boolean, nullable=False, default=False)
    update_time = db.Column(db.DateTime, nullable=True)
