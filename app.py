from flask_wtf import FlaskForm #type:ignore
from wtforms import StringField, PasswordField, SubmitField, DecimalField, IntegerField, SelectField,RadioField,BooleanField,TextAreaField #type:ignore
from wtforms.validators import DataRequired, Email, EqualTo#type:ignore
import pandas as pd#type:ignore
import numpy as np#type:ignore
from functools import wraps#type:ignore
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, redirect, url_for, render_template, request, flash, session#type:ignore
import os

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('You must be logged in to access that page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function
@login_required
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'type' != "Admin":
            return "Access Denied"
        return f(*args, **kwargs)
    return decorated_function

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class UPIForm(FlaskForm):
    to = StringField("To")
    amount = IntegerField("Amount")
    submit = SubmitField("Submit")

class ATMForm(FlaskForm):
    amount = IntegerField("Amount")
    submit = SubmitField("Submit")

class SignUpForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(message='Email required'), Email()])
    username = StringField('Username', validators=[DataRequired(message='Username required')])
    password = PasswordField('Password', validators=[DataRequired(message='Password required')])
    pass_conform = PasswordField('Conform Password',
                                 validators=[DataRequired(message='Please conform password'),
                                             EqualTo('password', message='Passwords must match')])
 
    submit = SubmitField('Register')

app=Flask(__name__)
app.config['SECRET_KEY'] = 'TheCousins'
@app.route('/',methods=['GET','POST'])
def home():
    
    return render_template('index.html')
@app.route('/login',methods=['GET','POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        new_user = {
            "Email": form.email.data,
            "Password": form.password.data
        }
    
        df_users = pd.read_excel("users.xlsx")
    

        # Verify email and password match
        user = df_users[df_users['Email'] == new_user['Email']]
        if not user.empty and user.iloc[0]['Password'] == new_user['Password']:
            session['user'] = new_user['Email'] 
            session['type']  = user['Type'].values[0] # Store user session
            messages = []
            flash('Login successful!', 'success')
            return redirect(url_for('home'))

    flash('User not found or incorrect password.', 'danger')
    return render_template('login.html', form=form)
@app.route('/logout')
@login_required 
def logout():
    session.pop('user', None)
    session.pop('type',None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))
@app.route("/UPI", methods=['GET', 'POST'])
@login_required
def UPI():
    form = UPIForm()
    df = pd.read_excel("users.xlsx")

    # Get current user's balance
    current_email = session['user']
    current_index = df[df['Email'] == current_email].index[0]
    current_amount = df.loc[current_index, 'Amount']

    if form.validate_on_submit():
        username_to = form.to.data
        amount = form.amount.data

        # Check if recipient exists
        if username_to in df['Username'].values:
            recipient_index = df[df['Username'] == username_to].index[0]

            # Check if user has enough balance
            if df.loc[current_index, 'Amount'] >= amount:
                # Perform transfer
                df.loc[recipient_index, 'Amount'] += amount
                df.loc[current_index, 'Amount'] -= amount

                # Save updated balances
                df.to_excel("users.xlsx", index=False)

                flash("Transaction successful!", "success")
                return redirect(url_for('UPI'))
            else:
                flash("Insufficient funds.", "danger")
        else:
            flash("Recipient username not found.", "warning")

    return render_template("UPI.html", form=form, current_amount=current_amount)


def get_chat_file(user1, user2):
    users_sorted = sorted([user1, user2])
    return os.path.join("Messages", f"{users_sorted[0]}-{users_sorted[1]}.xlsx")


@app.route("/CousinsCorner",methods = ['GET','POST'])
@login_required
def CousinsCorner():
    users_df = pd.read_excel("users.xlsx")
    users_names = users_df['Username'].tolist()
    os.makedirs("Messages", exist_ok=True)

    # Get current logged-in username from email
    user_email = session.get('user')
    sender = users_df[users_df['Email'] == user_email]['Username'].iloc[0]

    if request.method == 'POST':
        # User selected a contact to chat with
        if 'contact-name' in request.form:
            current_user = request.form.get("contact-name")
            session['current_user'] = current_user

        # User sent a message
        else:
            current_user = session.get('current_user')
            if not current_user:
                return "No contact selected. Please select a user first.", 400

            message_text = request.form.get("message")
            chat_file = get_chat_file(sender, current_user)

            if os.path.exists(chat_file):
                df = pd.read_excel(chat_file)
            else:
                df = pd.DataFrame(columns=["text", "sender"])

            df = pd.concat([df, pd.DataFrame([{
                "text": message_text,
                "sender": sender
            }])], ignore_index=True)

            df.to_excel(chat_file, index=False)

        # Load messages after send/select
        current_user = session.get('current_user')
        chat_file = get_chat_file(sender, current_user)

        if os.path.exists(chat_file):
            df = pd.read_excel(chat_file)
        else:
            df = pd.DataFrame(columns=["text", "sender"])

        messages = []
        for row in df.itertuples(index=False):
            messages.append({
                "text": row.text,
                "sender": "You" if row.sender == sender else row.sender
            })

        return render_template("CousinsCorner.html", users_names=users_names, messages=messages, selected_user=current_user)

    # GET request
    return render_template("CousinsCorner.html", users_names=users_names, messages=[], selected_user=None)

@app.route('/ATM', methods=['GET', 'POST'])
@login_required
def ATM():
    form = ATMForm()
    df = pd.read_excel("users.xlsx")

    # Get current user's email and balance
    current_email = session['user']
    current_index = df[df['Email'] == current_email].index[0]
    current_amount = df.loc[current_index, 'Amount']

    if form.validate_on_submit():
        amount = form.amount.data

        # Check if the user has enough balance
        if current_amount >= amount:
            # Update the balance using .loc to avoid SettingWithCopyWarning
            df.loc[current_index, 'Amount'] -= amount

            # Save the updated balance
            df.to_excel("users.xlsx", index=False)

            flash(f"{amount} withdrawn successfully!", "success")
            return redirect(url_for('ATM'))
        else:
            flash("Insufficient balance.", "danger")

    return render_template("ATM.html", form=form, current_amount=current_amount)


@app.route('/SignUp')
def sign_up():
    form = SignUpForm()
    if form.validate_on_submit():
        new_user = {
            "Username": form.username.data,
            "Email": form.email.data,
            "Password": form.password.data,
            "Type" : "Member",
            "Amount":  15000000
        }
        import os

        # Replace with your desired folder path
        folder_path = f"{new_user['Email']}"

        # Create the folder (if it doesn't already exist)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            print("Folder created!")
        else:
            print("Folder already exists.")

        # Load existing users
        df_users = pd.read_excel("users.xlsx")
     

        # Check for duplicates
        if ((df_users['Username'] == new_user["Username"]).any() or
            (df_users['Email'] == new_user["Email"]).any()):
            flash('Username or Email already exists. Please choose a different one.', 'danger')
        else:
            df_users = pd.concat([df_users, pd.DataFrame([new_user])], ignore_index=True)
            df_users.to_excel("users.xlsx", index=False)
            flash('Registration successful! You can now log in.', 'success')
            return redirect(url_for('login'))

    return render_template('sign_up.html', form=form)

if __name__ == '__main__':
    #DEBUG is SET to TRUE. CHANGE FOR PROD
    app.run(port=5000,debug=True)