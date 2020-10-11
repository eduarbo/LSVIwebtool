from flask.cli import FlaskGroup

from project import app
#from web.project.database_setup2 import Base, engine
from project.database_setup import db, tracker

cli = FlaskGroup(app)


@cli.command("create_db")
def create_db():
    db.drop_all()
    db.create_all()
    db.session.commit()

@cli.command("seed_db")
def seed_db():
    newentry = tracker(project='My first project',
                       room='room test',
                       name='Omar Ruiz',
                       afilliation='Durham University',
                       email='omar.a.ruiz-macias@durham.ac.uk',
                       progress=int(0),
                       status='open',
                       author=False
                       )

    db.session.add(newentry)
    db.session.commit()

if __name__ == "__main__":
    cli()
