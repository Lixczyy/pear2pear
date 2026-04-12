from flask import Flask, render_template, request, redirect, url_for
from time import *
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
app= Flask(__name__)

class LoginForm(FlaskForm):
    username = StringField('Username')
    password = PasswordField('Password')
    submit = SubmitField('Login')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/account')
def account():
    return render_template('account.html')

@app.route('/logout')
def logout():
    return render_template('logout.html')

if __name__ == '__main__':
    app.run(debug=True) 