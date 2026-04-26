from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), default='student')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    resources = db.relationship('Resource', backref='uploader', lazy=True)

class Resource(db.Model):
    __tablename__ = 'resources'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    semester = db.Column(db.Integer, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    file_path = db.Column(db.String(500), nullable=False)
    file_size_mb = db.Column(db.Float)
    uploader_name = db.Column(db.String(255))
    uploader_email = db.Column(db.String(255))
    status = db.Column(db.String(50), default='pending')
    download_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

class DiscussionThread(db.Model):
    __tablename__ = 'discussion_threads'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(255), nullable=False)
    author_email = db.Column(db.String(255))
    subject = db.Column(db.String(100))
    category = db.Column(db.String(50), default='general')
    view_count = db.Column(db.Integer, default=0)
    reply_count = db.Column(db.Integer, default=0)
    is_pinned = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Comment(db.Model):
    __tablename__ = 'comments'
    
    id = db.Column(db.Integer, primary_key=True)
    thread_id = db.Column(db.Integer, db.ForeignKey('discussion_threads.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(255), nullable=False)
    author_email = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    thread = db.relationship('DiscussionThread', backref='comments', lazy=True)

# Helper functions
def get_resources_by_subject(subject=None, semester=None, category=None, status='approved'):
    query = Resource.query.filter_by(status=status)
    if subject:
        query = query.filter_by(subject=subject)
    if semester:
        query = query.filter_by(semester=semester)
    if category:
        query = query.filter_by(category=category)
    return query.order_by(Resource.created_at.desc()).all()

def get_threads_by_subject(subject=None, category=None):
    query = DiscussionThread.query.order_by(DiscussionThread.is_pinned.desc(), DiscussionThread.created_at.desc())
    if subject:
        query = query.filter_by(subject=subject)
    if category:
        query = query.filter_by(category=category)
    return query.all()

def get_comments_by_thread(thread_id):
    return Comment.query.filter_by(thread_id=thread_id).order_by(Comment.created_at.asc()).all()

def increment_download_count(resource_id):
    resource = Resource.query.get(resource_id)
    if resource:
        resource.download_count += 1
        db.session.commit()
        return True
    return False
