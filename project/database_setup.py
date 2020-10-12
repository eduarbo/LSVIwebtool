
from flask_sqlalchemy import SQLAlchemy
#from project import app
db = SQLAlchemy()

def init_app(app):
    db.init_app(app)





