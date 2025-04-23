from app import db  # Make sure you're importing the db object correctly

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    email_address = db.Column(db.String(120), nullable=False, unique=True)
    google_id = db.Column(db.String(120), nullable=False, unique=True)
    is_verified = db.Column(db.Boolean, default=False)
    picture = db.Column(db.String(255))  # New column for the profile picture

    def __repr__(self):
        return f'<User {self.username}>'
