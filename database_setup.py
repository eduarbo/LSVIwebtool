
# for creating the mapper code
from sqlalchemy import Column, ForeignKey, Integer, String, Boolean

# for configuration and class code
from sqlalchemy.ext.declarative import declarative_base

# for configuration
from sqlalchemy import create_engine

# create declarative_base instance
Base_tracker = declarative_base()
Base_projects = declarative_base()

class tracker(Base_tracker):
    __tablename__ = 'VItracker'

    id = Column(Integer, primary_key=True)
    project = Column(String(250), nullable=False)
    room = Column(String(250), nullable=False)
    batch = Column(Integer, nullable=False)
    name = Column(String(250), nullable=False)
    afilliation = Column(String(250), nullable=False)
    email = Column(String(250), nullable=False)
    progress = Column(Integer)
    status = Column(String(250), nullable=False)

class VIprojects(Base_projects):
    __tablename__ = 'projects'

    id = Column(Integer, primary_key=True)
    project = Column(String(250), nullable=False)
    project_description = Column(String(500), nullable=False)
    room = Column(String(250), nullable=False)
    name = Column(String(250), nullable=False)
    afilliation = Column(String(250), nullable=False)
    email = Column(String(250), nullable=False)
    VIreq = Column(Integer, nullable=False)
    progress = Column(Integer)
    status = Column(String(250), nullable=False)
    VI = Column(Boolean, default=True)

# creates a create_engine instance at the bottom of the file
engine_tracker = create_engine('sqlite:///vi-tracker.db')
engine_projects = create_engine('sqlite:///vi-projects.db')

Base_tracker.metadata.create_all(engine_tracker)
Base_projects.metadata.create_all(engine_projects)
