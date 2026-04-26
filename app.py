from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import uuid
from datetime import datetime
from supabase import create_client, Client
import psycopg2
from psycopg2.extras import RealDictCursor

# Initialize Flask app
app = Flask(__name__, 
            template_folder='templates',
            static_folder='static')
app.secret_key = os.getenv('SECRET_KEY', os.urandom(24))
CORS(app)

# Supabase configuration (REQUIRED for file storage on Vercel)
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

# Database configuration (PostgreSQL - REQUIRED, no SQLite on Vercel)
DATABASE_URL = os.getenv('DATABASE_URL')

# Remove UPLOAD_FOLDER - we're using Supabase Storage instead
# DO NOT create any directories on Vercel filesystem

def get_db_connection():
    """Get database connection for PostgreSQL"""
    if not DATABASE_URL:
        print("DATABASE_URL not set")
        return None
    try:
        return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def init_database():
    """Initialize database tables - safe to run on every startup"""
    conn = get_db_connection()
    if not conn:
        print("No database connection available. Skipping table creation.")
        return
    
    try:
        cur = conn.cursor()
        
        # Create resources table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS resources (
                id SERIAL PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                subject VARCHAR(100) NOT NULL,
                semester INTEGER NOT NULL,
                category VARCHAR(50) NOT NULL,
                description TEXT,
                file_url TEXT NOT NULL,
                file_name VARCHAR(255),
                file_size_mb DECIMAL(10,2),
                uploader_name VARCHAR(255),
                uploader_email VARCHAR(255),
                status VARCHAR(50) DEFAULT 'pending',
                download_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create discussions table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS discussions (
                id SERIAL PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                content TEXT NOT NULL,
                author VARCHAR(255) NOT NULL,
                author_email VARCHAR(255),
                subject VARCHAR(100),
                category VARCHAR(50) DEFAULT 'general',
                view_count INTEGER DEFAULT 0,
                reply_count INTEGER DEFAULT 0,
                is_pinned BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create comments table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS comments (
                id SERIAL PRIMARY KEY,
                discussion_id INTEGER REFERENCES discussions(id) ON DELETE CASCADE,
                content TEXT NOT NULL,
                author VARCHAR(255) NOT NULL,
                author_email VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        print("Database tables initialized successfully")
    except Exception as e:
        print(f"Database initialization error: {e}")
    finally:
        cur.close()
        conn.close()

# Initialize database on startup
init_database()

# Constants
SUBJECTS = [
    {'name': 'Physics', 'icon': '⚛️', 'color': '#2563EB', 'path': 'physics', 
     'description': 'Classical & Quantum Mechanics, Thermodynamics, Electromagnetism'},
    {'name': 'Chemistry', 'icon': '🧪', 'color': '#D70A0A', 'path': 'chemistry', 
     'description': 'Organic, Inorganic, Physical Chemistry'},
    {'name': 'Mathematics', 'icon': '📐', 'color': '#0A192F', 'path': 'mathematics', 
     'description': 'Calculus, Algebra, Differential Equations'},
    {'name': 'Statistics', 'icon': '📊', 'color': '#00C853', 'path': 'statistics', 
     'description': 'Probability, Statistical Inference, Data Analysis'},
    {'name': 'Biology', 'icon': '🧬', 'color': '#7C3AED', 'path': 'biology', 
     'description': 'Molecular Biology, Genetics, Ecology'},
    {'name': 'Environmental Science', 'icon': '🌿', 'color': '#16A34A', 'path': 'environmental-science', 
     'description': 'Ecology, Climate Change, Sustainability'},
    {'name': 'Econometrics', 'icon': '📈', 'color': '#2563EB', 'path': 'econometrics', 
     'description': 'Economic Models, Data Analysis, Forecasting'},
    {'name': 'Photonics', 'icon': '🔆', 'color': '#F59E0B', 'path': 'photonics', 
     'description': 'Optics, Lasers, Light Technology'},
    {'name': 'Electives', 'icon': '📖', 'color': '#64748B', 'path': 'electives', 
     'description': 'Specialized Topics & Interdisciplinary Studies'},
]

SEMESTERS = [{'id': i, 'name': f'Semester {i}', 'type': 'Even' if i % 2 == 0 else 'Odd'} for i in range(1, 11)]

CATEGORIES = [
    {'value': 'question_paper', 'label': 'Question Paper', 'icon': '📄'},
    {'value': 'textbook', 'label': 'Textbook', 'icon': '📚'},
    {'value': 'student_notes', 'label': 'Student Notes', 'icon': '📝'},
]

def get_resources(filters=None):
    """Get resources from database"""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cur = conn.cursor()
        query = "SELECT * FROM resources WHERE status = 'approved'"
        params = []
        
        if filters:
            if filters.get('subject'):
                query += " AND subject = %s"
                params.append(filters['subject'])
            if filters.get('semester'):
                query += " AND semester = %s"
                params.append(filters['semester'])
            if filters.get('category'):
                query += " AND category = %s"
                params.append(filters['category'])
        
        query += " ORDER BY created_at DESC"
        
        cur.execute(query, params)
        resources = cur.fetchall()
        return resources
    except Exception as e:
        print(f"Error fetching resources: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def get_recent_resources(limit=6):
    """Get recent approved resources"""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM resources 
            WHERE status = 'approved' 
            ORDER BY created_at DESC 
            LIMIT %s
        """, (limit,))
        resources = cur.fetchall()
        return resources
    except Exception as e:
        print(f"Error fetching recent resources: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def get_discussions():
    """Get discussions from database"""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM discussions 
            ORDER BY is_pinned DESC, created_at DESC
        """)
        discussions = cur.fetchall()
        return discussions
    except Exception as e:
        print(f"Error fetching discussions: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def upload_to_supabase(file, filename):
    """Upload file to Supabase storage"""
    if not supabase:
        print("Supabase not configured")
        return None
    
    try:
        file_content = file.read()
        # Create a unique file path
        file_path = f"resources/{datetime.now().strftime('%Y/%m/%d')}/{uuid.uuid4().hex}_{secure_filename(filename)}"
        
        # Upload to Supabase storage
        supabase.storage.from_('resources').upload(file_path, file_content)
        
        # Get public URL
        public_url = supabase.storage.from_('resources').get_public_url(file_path)
        return public_url
    except Exception as e:
        print(f"Upload error: {e}")
        return None

# Routes
@app.route('/')
def index():
    """Home page"""
    recent_resources = get_recent_resources()
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
    """Subject page"""
    subject = next((s for s in SUBJECTS if s['path'] == path), None)
    if not subject:
        return redirect(url_for('library'))
    
    resources = get_resources({'subject': subject['name']})
    return render_template('subject.html', 
                         subject=subject, 
                         resources=resources, 
                         semesters=SEMESTERS, 
                         active_page='library')

@app.route('/resources')
def resources_page():
    """All resources page"""
    subject = request.args.get('subject')
    semester = request.args.get('semester', type=int)
    category = request.args.get('category')
    
    filters = {}
    if subject:
        filters['subject'] = subject
    if semester:
        filters['semester'] = semester
    if category:
        filters['category'] = category
    
    resources = get_resources(filters)
    return render_template('resources.html', 
                         resources=resources, 
                         subjects=SUBJECTS, 
                         semesters=SEMESTERS, 
                         categories=CATEGORIES,
                         current_subject=subject,
                         current_semester=semester,
                         current_category=category,
                         active_page='resources')

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
            return jsonify({'error': 'Missing required fields'}), 400
        
        if file.filename and not file.filename.endswith('.pdf'):
            return jsonify({'error': 'Only PDF files are allowed'}), 400
        
        # Generate unique filename
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secure_filename(file.filename)}"
        
        # Upload to Supabase (REQUIRED - no filesystem storage)
        file_url = upload_to_supabase(file, filename)
        
        if not file_url:
            return jsonify({'error': 'Failed to upload file. Please check Supabase configuration.'}), 500
        
        # Save to database
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO resources (title, subject, semester, category, description, 
                                     file_url, file_name, uploader_name, uploader_email, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')
            """, (title, subject, semester, category, description, file_url, filename, 
                  uploader_name, uploader_email))
            conn.commit()
            return jsonify({'success': True, 'message': 'Resource submitted for review'})
        except Exception as e:
            print(f"Database error: {e}")
            return jsonify({'error': 'Database error'}), 500
        finally:
            cur.close()
            conn.close()
    
    return render_template('upload.html', 
                         subjects=SUBJECTS, 
                         semesters=SEMESTERS, 
                         categories=CATEGORIES, 
                         active_page='upload')

@app.route('/discussions')
def discussions():
    """Discussion forum page"""
    discussions_list = get_discussions()
    return render_template('discussions.html', 
                         discussions=discussions_list, 
                         subjects=SUBJECTS,
                         active_page='discussions')

@app.route('/discussions/create', methods=['POST'])
def create_discussion():
    """Create new discussion"""
    data = request.get_json()
    
    title = data.get('title')
    content = data.get('content')
    author = data.get('author')
    author_email = data.get('author_email')
    subject = data.get('subject')
    category = data.get('category', 'general')
    
    if not all([title, content, author, subject]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO discussions (title, content, author, author_email, subject, category)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (title, content, author, author_email, subject, category))
        discussion_id = cur.fetchone()['id']
        conn.commit()
        return jsonify({'success': True, 'id': discussion_id})
    except Exception as e:
        print(f"Database error: {e}")
        return jsonify({'error': 'Database error'}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/discussions/<int:discussion_id>')
def view_discussion(discussion_id):
    """View individual discussion"""
    conn = get_db_connection()
    if not conn:
        return "Database error", 500
    
    try:
        cur = conn.cursor()
        
        # Get discussion
        cur.execute("SELECT * FROM discussions WHERE id = %s", (discussion_id,))
        discussion = cur.fetchone()
        
        if not discussion:
            return "Discussion not found", 404
        
        # Increment view count
        cur.execute("UPDATE discussions SET view_count = view_count + 1 WHERE id = %s", (discussion_id,))
        conn.commit()
        
        # Get comments
        cur.execute("SELECT * FROM comments WHERE discussion_id = %s ORDER BY created_at ASC", (discussion_id,))
        comments = cur.fetchall()
        
        return render_template('discussion.html', 
                             discussion=discussion, 
                             comments=comments,
                             active_page='discussions')
    except Exception as e:
        print(f"Error: {e}")
        return "Error loading discussion", 500
    finally:
        cur.close()
        conn.close()

@app.route('/discussions/<int:discussion_id>/comment', methods=['POST'])
def add_comment(discussion_id):
    """Add comment to discussion"""
    data = request.get_json()
    
    content = data.get('content')
    author = data.get('author')
    author_email = data.get('author_email')
    
    if not all([content, author]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO comments (discussion_id, content, author, author_email)
            VALUES (%s, %s, %s, %s)
        """, (discussion_id, content, author, author_email))
        
        # Update reply count
        cur.execute("""
            UPDATE discussions 
            SET reply_count = reply_count + 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (discussion_id,))
        
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': 'Database error'}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/api/stats')
def api_stats():
    """API endpoint for statistics"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database not available'}), 503
    
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as total FROM resources WHERE status = 'approved'")
        total_resources = cur.fetchone()['total']
        
        cur.execute("SELECT COALESCE(SUM(download_count), 0) as total FROM resources")
        total_downloads = cur.fetchone()['total']
        
        cur.execute("SELECT COUNT(*) as total FROM discussions")
        total_discussions = cur.fetchone()['total']
        
        return jsonify({
            'total_resources': total_resources,
            'total_downloads': total_downloads,
            'total_discussions': total_discussions,
            'total_subjects': len(SUBJECTS),
            'total_semesters': len(SEMESTERS)
        })
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': 'Database error'}), 500
    finally:
        cur.close()
        conn.close()

# Error handlers
@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500

# Vercel handler - DO NOT call app.run() on Vercel
# The app object is exported for Vercel serverless functions
