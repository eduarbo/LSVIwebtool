
from flask_sqlalchemy import SQLAlchemy
from project import app

app.config.from_object("project.config.Config")
db = SQLAlchemy(app)

class tracker(db.Model):
    __tablename__ = 'vitracker'

    #common
    id = db.Column(db.Integer, primary_key=True)
    project = db.Column(db.String(250), nullable=False)
    room = db.Column(db.String(250), nullable=False)
    name = db.Column(db.String(250), nullable=False)
    afilliation = db.Column(db.String(250), nullable=False)
    email = db.Column(db.String(250), nullable=False)
    progress = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(250), nullable=False)
    author = db.Column(db.Boolean, nullable=False)
    vi_query = db.Column(db.PickleType, nullable=True)

    #for joiners,
    batch = db.Column(db.Integer, nullable=True)
    room_id = db.Column(db.Integer, nullable=True)


    #for authors
    vi = db.Column(db.Boolean, default=True)
    vi_req = db.Column(db.Integer, nullable=True)
    project_description = db.Column(db.String, nullable=True)
    ncols = db.Column(db.Integer, nullable=True)
    batchsize = db.Column(db.Integer, nullable=True)
    boxsize = db.Column(db.Integer, nullable=True)
    nbatchs = db.Column(db.Integer, nullable=True)
    ncentres = db.Column(db.Integer, nullable=True)
    batchs_idx = db.Column(db.PickleType, nullable=True)
    ndata = db.Column(db.Integer, nullable=True)
    coord_names = db.Column(db.PickleType, nullable=True)
    labels = db.Column(db.PickleType, nullable=True)
    info_list = db.Column(db.PickleType, nullable=True)
    layers = db.Column(db.PickleType, nullable=True)
    centres = db.Column(db.String(250), nullable=True)
    vi_labels = db.Column(db.PickleType, nullable=True)
    plots = db.Column(db.PickleType, nullable=True)


