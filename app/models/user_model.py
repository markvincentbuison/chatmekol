from flask_login import UserMixin
from app.extensions import db  # change if your DB import is different

class User(UserMixin):
    def __init__(self, id=None, email=None, name=None):
        self.id = id
        self.email = email
        self.name = name

    @staticmethod
    def get_by_email(email):
        cursor = db.connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        result = cursor.fetchone()
        if result:
            return User(id=result["id"], email=result["email"], name=result["name"])
        return None

    def save_to_db(self):
        cursor = db.connection.cursor()
        cursor.execute("INSERT INTO users (email, name) VALUES (%s, %s)", (self.email, self.name))
        db.connection.commit()
