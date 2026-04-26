import os
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from database import db, Resource, DiscussionThread, Comment, get_resources_by_subject, get_threads_by_subject, get_comments_by_thread, increment_download_count

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///library.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'pdf'}

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize extensions
CORS(app)
db.init_app(app)

# Create tables
with app.app_context():
    db.create_all()

# Constants
SUBJECTS = [
    {'name': 'Physics', 'icon': '⚛️', 'color': '#2563EB', 'path': 'physics'},
    {'name': 'Chemistry', 'icon': '🧪', 'color': '#D70A0A', 'path': 'chemistry'},
    {'name': 'Mathematics', 'icon': '📐', 'color': '#0A192F', 'path': 'mathematics'},
    {'name': 'Statistics', 'icon': '📊', 'color': '#00C853', 'path': 'statistics'},
    {'name': 'Biology', 'icon': '🧬', 'color': '#7C3AED', 'path': 'biology'},
    {'name': 'Environmental Science', 'icon': '🌿', 'color': '#16A34A', 'path': 'environmental-science'},
    {'name': 'Econometrics', 'icon': '📈', 'color': '#2563EB', 'path': 'econometrics'},
    {'name': 'Photonics', 'icon': '🔆', 'color': '#F59E0B', 'path': 'photonics'},
    {'name': 'Electives', 'icon': '📖', 'color': '#64748B', 'path': 'electives'},
]

SEMESTERS = [{'id': i, 'name': f'Semester {i}', 'type': 'Even' if i % 2 == 0 else 'Odd'} for i in range(1, 11)]

CATEGORIES = [
    {'value': 'question_paper', 'label': 'Question Paper', 'icon': '📄'},
    {'value': 'textbook', 'label': 'Textbook', 'icon': '📚'},
    {'value': 'student_notes', 'label': 'Student Notes', 'icon': '📝'},
]

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Routes
@app.route('/')
def index():
    """Home page"""
    recent_resources = Resource.query.filter_by(status='approved').order_by(Resource.created_at.desc()).limit(6).all()
    return render_template('index.html', 
                         subjects=SUBJECTS, 
                         recent_resources=recent_resources,
                         active_page='home')

@app.route('/library')
def library():
    """Library page"""
    return render_template('library.html', subjects=SUBJECTS, active_page='library')

@app.route('/subject/<path>')
def subject_page(path):
    """Subject page with resources"""
    subject = next((s for s in SUBJECTS if s['path'] == path), None)
    if not subject:
        return redirect(url_for('library'))
    
    resources = get_resources_by_subject(subject=subject['name'])
    return render_template('subject.html', subject=subject, resources=resources, semesters=SEMESTERS, active_page='library')

@app.route('/resources')
def resources_page():
    """All resources page"""
    subject = request.args.get('subject')
    semester = request.args.get('semester', type=int)
    category = request.args.get('category')
    
    resources = get_resources_by_subject(subject=subject, semester=semester, category=category)
    return render_template('resources.html', 
                         resources=resources, 
                         subjects=SUBJECTS, 
                         semesters=SEMESTERS, 
                         categories=CATEGORIES,
                         current_subject=subject,
                         current_semester=semester,
                         current_category=category,
                         active_page='resources')

@app.route('/download/<int:resource_id>')
def download_resource(resource_id):
    """Download resource file"""
    resource = Resource.query.get_or_404(resource_id)
    if resource.status != 'approved':
        flash('This resource is not available for download yet.', 'error')
        return redirect(url_for('resources_page'))
    
    increment_download_count(resource_id)
    return send_from_directory(app.config['UPLOAD_FOLDER'], resource.file_path, as_attachment=True)

@app.route('/upload', methods=['GET', 'POST'])
def upload_resource():
    """Upload resource page"""
    if request.method == 'POST':
        title = request.form.get('title')
        subject = request.form.get('subject')
        semester = request.form.get('semester', type=int)
        category = request.form.get('category')
        description = request.form.get('description')
        uploader_name = request.form.get('uploader_name')
        uploader_email = request.form.get('uploader_email')
        
        file = request.files.get('file')
        
        if not all([title, subject, semester, category, uploader_name, uploader_email, file]):
            flash('Please fill in all required fields.', 'error')
            return redirect(url_for('upload_resource'))
        
        if not allowed_file(file.filename):
            flash('Only PDF files are allowed.', 'error')
            return redirect(url_for('upload_resource'))
        
        if file.content_length > 50 * 1024 * 1024:
            flash('File size exceeds 50MB limit.', 'error')
            return redirect(url_for('upload_resource'))
        
        filename = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
        
        resource = Resource(
            title=title,
            subject=subject,
            semester=semester,
            category=category,
            description=description,
            file_path=filename,
            file_size_mb=round(file_size_mb, 2),
            uploader_name=uploader_name,
            uploader_email=uploader_email,
            status='pending'
        )
        
        db.session.add(resource)
        db.session.commit()
        
        flash('Resource submitted successfully! Our team will review it shortly.', 'success')
        return redirect(url_for('upload_resource'))
    
    return render_template('upload.html', subjects=SUBJECTS, semesters=SEMESTERS, categories=CATEGORIES, active_page='upload')

@app.route('/discussions')
def discussions():
    """Discussion forum page"""
    subject = request.args.get('subject')
    category = request.args.get('category')
    threads = get_threads_by_subject(subject=subject, category=category)
    return render_template('discussions.html', 
                         threads=threads, 
                         subjects=SUBJECTS, 
                         categories=['general', 'help', 'resources', 'tips', 'important'],
                         current_subject=subject,
                         current_category=category,
                         active_page='discussions')

@app.route('/discussions/new', methods=['POST'])
def create_thread():
    """Create new discussion thread"""
    data = request.get_json() if request.is_json else request.form
    
    title = data.get('title')
    content = data.get('content')
    author = data.get('author')
    author_email = data.get('author_email')
    subject = data.get('subject')
    category = data.get('category', 'general')
    
    if not all([title, content, author, subject]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    thread = DiscussionThread(
        title=title,
        content=content,
        author=author,
        author_email=author_email,
        subject=subject,
        category=category
    )
    
    db.session.add(thread)
    db.session.commit()
    
    return jsonify({'success': True, 'thread_id': thread.id})

@app.route('/discussions/<int:thread_id>')
def view_thread(thread_id):
    """View individual thread"""
    thread = DiscussionThread.query.get_or_404(thread_id)
    thread.view_count += 1
    db.session.commit()
    
    comments = get_comments_by_thread(thread_id)
    return render_template('thread.html', thread=thread, comments=comments, active_page='discussions')

@app.route('/discussions/<int:thread_id>/comment', methods=['POST'])
def add_comment(thread_id):
    """Add comment to thread"""
    data = request.get_json() if request.is_json else request.form
    
    content = data.get('content')
    author = data.get('author')
    author_email = data.get('author_email')
    
    if not all([content, author]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    comment = Comment(
        thread_id=thread_id,
        content=content,
        author=author,
        author_email=author_email
    )
    
    thread = DiscussionThread.query.get(thread_id)
    if thread:
        thread.reply_count += 1
    
    db.session.add(comment)
    db.session.commit()
    
    return jsonify({'success': True, 'comment_id': comment.id})

@app.route('/api/resources')
def api_resources():
    """API endpoint for resources"""
    subject = request.args.get('subject')
    semester = request.args.get('semester', type=int)
    category = request.args.get('category')
    
    resources = get_resources_by_subject(subject=subject, semester=semester, category=category)
    return jsonify([{
        'id': r.id,
        'title': r.title,
        'subject': r.subject,
        'semester': r.semester,
        'category': r.category,
        'description': r.description,
        'file_size_mb': r.file_size_mb,
        'uploader_name': r.uploader_name,
        'download_count': r.download_count,
        'created_at': r.created_at.isoformat() if r.created_at else None
    } for r in resources])

@app.route('/api/stats')
def api_stats():
    """API endpoint for statistics"""
    total_resources = Resource.query.filter_by(status='approved').count()
    total_downloads = db.session.query(db.func.sum(Resource.download_count)).scalar() or 0
    total_threads = DiscussionThread.query.count()
    total_comments = Comment.query.count()
    
    return jsonify({
        'total_resources': total_resources,
        'total_downloads': total_downloads,
        'total_threads': total_threads,
        'total_comments': total_comments
    })

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
