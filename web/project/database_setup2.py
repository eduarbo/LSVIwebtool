
# for creating the mapper code
from sqlalchemy import Column, ForeignKey, Integer, String, Boolean, PickleType

# for configuration and class code
from sqlalchemy.ext.declarative import declarative_base

# for configuration
from sqlalchemy import create_engine

# create declarative_base instance
Base = declarative_base()

class tracker(Base):
    __tablename__ = 'VI-tracker'

    #common
    id = Column(Integer, primary_key=True)
    project = Column(String(250), nullable=False)
    room = Column(String(250), nullable=False)
    name = Column(String(250), nullable=False)
    afilliation = Column(String(250), nullable=False)
    email = Column(String(250), nullable=False)
    progress = Column(Integer, nullable=False, default=0)
    status = Column(String(250), nullable=False)
    author = Column(Boolean, nullable=False)
    vi_query = Column(PickleType, nullable=True)

    #for joiners,
    batch = Column(Integer, nullable=True)
    room_id = Column(Integer, nullable=True)


    #for authors
    vi = Column(Boolean, default=True)
    vi_req = Column(Integer, nullable=True)
    project_description = Column(String, nullable=True)
    ncols = Column(Integer, nullable=True)
    batchsize = Column(Integer, nullable=True)
    boxsize = Column(Integer, nullable=True)
    nbatchs = Column(Integer, nullable=True)
    ncentres = Column(Integer, nullable=True)
    batchs_idx = Column(PickleType, nullable=True)
    ndata = Column(Integer, nullable=True)
    coord_names = Column(PickleType, nullable=True)
    labels = Column(PickleType, nullable=True)
    info_list = Column(PickleType, nullable=True)
    layers = Column(PickleType, nullable=True)
    centres = Column(String(250), nullable=True)
    vi_labels = Column(PickleType, nullable=True)
    plots = Column(PickleType, nullable=True)



# creates a create_engine instance at the bottom of the file
engine = create_engine('sqlite:///vi-tracker.db')
Base.metadata.create_all(engine)

