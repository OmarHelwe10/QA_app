from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import os
from database_helpers import get_db, close_db
from bson.objectid import ObjectId

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.teardown_appcontext(close_db)

def get_current_user():
    """Retrieve the current user from the session."""
    db = get_db()
    users_collection = db.users
    if 'user' in session:
        user_name = session['user']
        user = users_collection.find_one({'name': user_name})
        return user, db, users_collection
    return None, db, users_collection

@app.route('/')
def index():
    """Render the home page with a list of questions."""
    user, db, users_collection = get_current_user()
    
    questions_collection = db.questions
    questions = questions_collection.find({'answer_text': {"$ne": ''}})
    
    question_asked_by_list = []
    for question in questions:
        asked_by = users_collection.find_one({'_id': question['asked_by_id']})
        answered_by = users_collection.find_one({'_id': question['expert_id']})
        question_asked_by_list.append({
            'question_id': question['_id'],
            'question': question['question_text'],
            'asked_by': asked_by['name'] if asked_by else 'Unknown',
            'expert': answered_by['name'] if answered_by else 'Unknown'
        })
    
    return render_template('home.html', user=user, question_asked_by_list=question_asked_by_list)

@app.route('/register', methods=['POST', 'GET'])
def register():
    """Handle user registration."""
    user, db, users_collection = get_current_user()
    
    if request.method == 'POST':
        existing_user = users_collection.find_one({'name': request.form['name']})
        if existing_user:
            return render_template('register.html', user=user, error='User already registered')

        hashed_password = generate_password_hash(request.form['password'], method='pbkdf2:sha256')
        result = users_collection.insert_one({
            'name': request.form['name'],
            'password': hashed_password,
            'expert': '0',
            'admin': '0'
        })
        if request.form['name'] == 'admin':
            users_collection.update_one({'name': 'admin'}, {'$set': {'admin': '1'}})
        session['user'] = request.form['name']
        return redirect(url_for('index'))
    
    return render_template('register.html', user=user)

@app.route('/login', methods=['POST', 'GET'])
def login():
    """Handle user login."""
    user, db, users_collection = get_current_user()
    
    if request.method == 'POST':
        name = request.form['name']
        password = request.form['password']
        user = users_collection.find_one({'name': name})
        
        if not user:
            return render_template('login.html', error='User not found')
        if not check_password_hash(user['password'], password):
            return render_template('login.html', error='Invalid password')
        
        session['user'] = user['name']
        return redirect(url_for('index'))
    
    return render_template('login.html', user=user)

@app.route('/logout')
def logout():
    """Handle user logout."""
    session.pop('user', None)
    return redirect(url_for('index'))

@app.route('/users')
def users():
    """Render the users management page."""
    user, db, users_collection = get_current_user()
    if not user:
        return redirect(url_for('login'))
    if user['admin'] == '0':
        return redirect(url_for('index'))
    
    users_list = users_collection.find({})
    return render_template('users.html', user=user, user_list=users_list)

@app.route('/promote/<user_id>')
def promote(user_id):
    """Promote a user to expert."""
    user, db, users_collection = get_current_user()
    if not user:
        return redirect(url_for('login'))
    if user['admin'] == '0':
        return redirect(url_for('index'))
    
    users_collection.update_one({'_id': ObjectId(user_id)}, {'$set': {'expert': '1'}})
    return redirect(url_for('users'))

@app.route('/ask', methods=['POST', 'GET'])
def ask():
    """Handle asking a question."""
    user, db, users_collection = get_current_user()
    if not user:
        return redirect(url_for('login'))
    
    questions_collection = db.questions
    if request.method == 'POST':
        question_text = request.form['question']
        if question_text:
            questions_collection.insert_one({
                'question_text': question_text,
                'answer_text': '',
                'asked_by_id': ObjectId(user['_id']),
                'expert_id': ObjectId(request.form['expert']),
            })
            return redirect(url_for('index'))
        return redirect(url_for('ask'))
    
    experts = users_collection.find({'expert': '1'})
    return render_template('ask.html', user=user, experts=experts)

@app.route('/unanswered')
def unanswered():
    """Render the page for unanswered questions."""
    user, db, users_collection = get_current_user()
    if not user:
        return redirect(url_for('login'))
    if user['expert'] == '0':
        return redirect(url_for('index'))
    
    questions_collection = db.questions
    questions = questions_collection.find({'answer_text': '',
                                           'expert_id': ObjectId(user['_id'])
                                           })
    
    question_asked_by_list = []
    for question in questions:
        asked_by = users_collection.find_one({'_id': question['asked_by_id']})
        question_asked_by_list.append({
            'question_id': question['_id'],
            'question': question['question_text'],
            'asked_by': asked_by['name'] if asked_by else 'Unknown',
        })
    
    return render_template('unanswered.html', user=user, question_asked_by_list=question_asked_by_list)

@app.route('/answer/<question_id>', methods=['GET', 'POST'])
def answer(question_id):
    """Handle answering a question."""
    user, db, users_collection = get_current_user()
    if not user:
        return redirect(url_for('login'))
    if user['expert'] == '0':
        return redirect(url_for('index'))
    
    questions_collection = db.questions
    if request.method == 'POST':
        answer_text = request.form['answer']
        questions_collection.update_one({'_id': ObjectId(question_id)}, {'$set': {'answer_text': answer_text}})
        return redirect(url_for('unanswered'))
    
    question = questions_collection.find_one({'_id': ObjectId(question_id)})
    return render_template('answer.html', user=user, question=question)

@app.route('/question/<question_id>')
def question(question_id):
    """Render the page for a specific question."""
    user, db, users_collection = get_current_user()
    questions_collection = db.questions
    question = questions_collection.find_one({'_id': ObjectId(question_id)})
    return render_template('question.html', user=user, question=question)

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5500))
    app.run(debug=True, host='0.0.0.0', port=port)
