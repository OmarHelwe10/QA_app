from flask import Flask,render_template,request,redirect,url_for,session
from werkzeug.security import generate_password_hash,check_password_hash
import os
from database_helpers import get_db,close_db
from bson.objectid import ObjectId
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.teardown_appcontext(close_db)

def get_current_user():
    user_result=None
    db=get_db()
    users_collection=db.users
    if 'user' in session:
        user = session['user']
        user_result=users_collection.find_one({'name':user})
    return user_result,db,users_collection

@app.route('/')
def index():
    (user,db,users_collection)=get_current_user()
    questions_collection=db.questions
    questions = questions_collection.find({'answer_text':{"$ne":''}})
    question_asked_by_list = []

    for question in questions:
        asked_by = users_collection.find_one({'_id': question['asked_by_id']})
        answered_by=users_collection.find_one({'_id': question['expert_id']})
        question_asked_by_list.append({
            'question_id': question['_id'],
            'question': question['question_text'],
            'asked_by': asked_by['name'],
            'expert':answered_by['name']
        })

    
    return render_template('home.html',user=user,question_asked_by_list=question_asked_by_list)

@app.route('/register',methods=['POST','GET'])
def register():
    user,db,users_collection=get_current_user() 


    if request.method == 'POST':
        check_users=users_collection.find_one({'name':request.form['name']})
        if check_users:
            return render_template('register.html',user=user,error='User already registered')

        hashed_password=generate_password_hash(request.form['password'],method='pbkdf2:sha256')
        result=users_collection.insert_one({
            'name': request.form['name'],
            'password': hashed_password,
            'expert': '0',
            'admin':'0'
        })
        print(result.inserted_id)
        #check if registering as admin
        if request.form['name']=='admin':
            users_collection.update_one({'name':'admin'},{'$set':{'admin':'1'}})
        #initialize session
        session['user']=request.form['name']
        return redirect(url_for('index'))   
        
        
    return render_template('register.html',user=user)

@app.route('/login',methods=['POST','GET'])
def login():
    user,db,users_collection=get_current_user() 

    
    if request.method == 'POST':
        name=request.form['name']
        password=request.form['password']
        user=users_collection.find_one({'name':name})
        
        if not user:
            
            return render_template(('login.html'),error='User not found')
        elif not check_password_hash(user['password'],password):
            return render_template(('login.html'),error='Invalid password')
        
        session['user'] = user['name']   
        return redirect(url_for('index'))
    return render_template('login.html',user=user)
    

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))


@app.route('/users')
def users():
    user,db,users_collection=get_current_user()
    if not user:
        return redirect(url_for('login'))
    if user['admin']=='0':
        return redirect(url_for('index'))
    users_list=users_collection.find({}) 
    #print(list(users_list))
    return render_template('users.html',user=user,user_list=users_list)

@app.route('/promote/<user_id>')
def promote(user_id):
    user,db,users_collection=get_current_user()
    if not user:
        return redirect(url_for('login'))
    if user['admin']=='0':
        return redirect(url_for('index'))
    users_collection.update_one({'_id': ObjectId(user_id)},{'$set':{'expert':'1'}})
    return redirect(url_for('users'))

@app.route('/ask',methods=['POST','GET'])
def ask():
    user,db,users_collection=get_current_user() 
    if not user:
        return redirect(url_for('login'))
    print(user)
    questions_collection=db.questions
    if request.method == 'POST':
        if request.form['question'] != '':
            
            question=questions_collection.insert_one({
                'question_text':request.form['question'],
                'answer_text':'',
                'asked_by_id':ObjectId(user['_id']),
               # 'asked_by_name':user['name'],
                'expert_id': ObjectId(request.form['expert']),
                                            })
            print(question.inserted_id)
            return redirect(url_for('index'))
        return redirect(url_for('ask'))
        
    experts=users_collection.find({'expert':'1'})
    
    return render_template('ask.html',user=user,experts=experts)



@app.route('/unanswered')
def unanswered():
    user, db, users_collection = get_current_user()
    if not user:
        return redirect(url_for('login'))
    if user['expert']=='0':
        return redirect(url_for('index'))    
    questions_collection = db.questions

    questions = questions_collection.find({'answer_text':''})
    question_asked_by_list = []

    for question in questions:
        asked_by = users_collection.find_one({'_id': question['asked_by_id']})
        question_asked_by_list.append({
            'question_id': question['_id'],
            'question': question['question_text'],
            'asked_by': asked_by['name'],
            
        })

    return render_template('unanswered.html', user=user, question_asked_by_list=question_asked_by_list)


@app.route('/answer/<question_id>',methods=['GET','POST'])
def answer(question_id):
    
    user,db,users_collection=get_current_user() 
    if not user:
        return redirect(url_for('login'))
    if user['expert']=='0':
        return redirect(url_for('index')) 
    questions_collection=db.questions
    if request.method == 'POST':
        answer_text=request.form['answer']
        print(answer_text)
        questions_collection.update_one({'_id': ObjectId(question_id)},{'$set':{'answer_text':answer_text}})
        return redirect(url_for('unanswered'))

    
    
    
    question=questions_collection.find_one({'_id': ObjectId(question_id)})
    

    return render_template('answer.html',user=user,question=question)

@app.route('/question/<question_id>')
def question(question_id):
    user,db,users_collection=get_current_user() 
    questions_collection = db.questions
    
    question=questions_collection.find_one({'_id': ObjectId(question_id)})
    
    return render_template('question.html',user=user,question=question)







if __name__ == '__main__':
    app.run(debug=True)