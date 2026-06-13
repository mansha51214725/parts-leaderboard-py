from flask import Flask, render_template, request, redirect, url_for, session
from datetime import datetime, timedelta
import sqlite3

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'

# ڈیٹا بیس کنکشن
def get_db():
    conn = sqlite3.connect('parts_leaderboard.db')
    conn.row_factory = sqlite3.Row
    return conn

# ڈیٹا بیس بنائیں
def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT UNIQUE NOT NULL,
            city TEXT DEFAULT 'Layyah',
            specialty TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            part_name TEXT,
            part_number TEXT NOT NULL,
            device_item TEXT NOT NULL,
            device_model TEXT,
            monthly_qty INTEGER DEFAULT 1,
            points INTEGER DEFAULT 5,
            is_shared INTEGER DEFAULT 0,
            submission_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()
    conn.close()

# ہوم پیج = رجسٹریشن
@app.route('/', methods=['GET', 'POST'])
def signup():
    message = ""
    error = ""
    
    if request.method == 'POST':
        name = request.form['name'].strip()
        phone = request.form['phone'].strip()
        city = request.form['city'].strip()
        specialty = request.form['specialty'].strip()
        
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE phone = ?', (phone,)).fetchone()
        
        if user:
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            message = "خوش آمدید! آپ پہلے سے رجسٹرڈ ہیں۔"
        else:
            conn.execute('INSERT INTO users (name, phone, city, specialty) VALUES (?, ?, ?, ?)',
                        (name, phone, city, specialty))
            conn.commit()
            session['user_id'] = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
            session['user_name'] = name
            message = "رجسٹریشن کامیاب! خوش آمدید۔"
        conn.close()
    
    return render_template('signup.html', message=message, error=error)

# لاگ آؤٹ
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('signup'))

# پرزہ درج کریں
@app.route('/submit', methods=['GET', 'POST'])
def submit_part():
    if 'user_id' not in session:
        return redirect(url_for('signup'))
    
    message = ""
    
    if request.method == 'POST':
        user_id = session['user_id']
        part_name = request.form['part_name'].strip()
        part_number = request.form['part_number'].strip()
        device_item = request.form['device_item'].strip()
        device_model = request.form['device_model'].strip()
        monthly_qty = int(request.form['monthly_qty'])
        
        conn = get_db()
        
        # چیک کریں کتنے مختلف صارفین نے یہ پرزہ + ڈیوائس ڈالا
        result = conn.execute('''
            SELECT COUNT(DISTINCT user_id) as cnt 
            FROM submissions 
            WHERE part_number = ? AND device_item = ?
        ''', (part_number, device_item)).fetchone()
        
        unique_users = result['cnt']
        
        if unique_users >= 1:
            points = 10
            is_shared = 1
        else:
            points = 5
            is_shared = 0
        
        conn.execute('''
            INSERT INTO submissions (user_id, part_name, part_number, device_item, device_model, monthly_qty, points, is_shared)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, part_name, part_number, device_item, device_model, monthly_qty, points, is_shared))
        
        # اگر مشترکہ ہے تو پچھلے سب کو 10 پوائنٹس کریں
        if is_shared == 1:
            conn.execute('''
                UPDATE submissions SET points = 10, is_shared = 1 
                WHERE part_number = ? AND device_item = ?
            ''', (part_number, device_item))
        
        conn.commit()
        conn.close()
        
        message = f"شکریہ! آپ کو {points} پوائنٹس ملے ہیں۔"
    
    return render_template('submit.html', message=message)

# لیڈر بورڈ
@app.route('/leaderboard')
def leaderboard():
    conn = get_db()
    
    three_months_ago = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
    
    leaders = conn.execute('''
        SELECT u.name, u.phone, u.specialty, 
               SUM(s.points) as total_points, 
               COUNT(s.id) as total_parts
        FROM submissions s 
        JOIN users u ON s.user_id = u.id 
        WHERE s.submission_date >= ?
        GROUP BY s.user_id 
        ORDER BY total_points DESC 
        LIMIT 10
    ''', (three_months_ago,)).fetchall()
    
    conn.close()
    
    return render_template('leaderboard.html', leaders=enumerate(leaders, 1))

# ایڈمن پینل
@app.route('/admin')
def admin():
    conn = get_db()
    
    shared_parts = conn.execute('''
        SELECT s.part_number, s.part_name, s.device_item,
               COUNT(DISTINCT s.user_id) as user_count,
               SUM(s.monthly_qty) as total_qty,
               MAX(s.submission_date) as last_request
        FROM submissions s 
        WHERE s.is_shared = 1 
        GROUP BY s.part_number, s.device_item 
        ORDER BY user_count DESC
    ''').fetchall()
    
    conn.close()
    
    return render_template('admin.html', shared_parts=shared_parts)

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)