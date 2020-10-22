
import os
import random
import shutil
from urllib.parse import urljoin

import pandas as pd

import numpy as np

from flask import Flask, redirect, url_for, render_template, request, flash, send_file, send_from_directory
from werkzeug.utils import secure_filename

from project.database_setup import db, init_app
from project.model import tracker
from project import commands

from rq import Queue
from project.worker import conn
from rq.job import Job

from project.lscutout import html_postages

app = Flask(__name__)

#q = Queue(connection=conn)

#app.config.from_object("project.config.DevelopmentConfig")
app.config.from_object(os.environ['APP_SETTINGS'])
app.config["DEBUG"] = os.environ['DEBUG']

commands.init_app(app)
init_app(app)

WHITENOISE_MAX_AGE = 31536000 if not app.config["DEBUG"] else 0
CDN = "https://d35wj5jfi7ws35.cloudfront.net"
app.config["STATIC_URL"] = CDN if not app.config["DEBUG"] else ""

# configure WhiteNoise
# app.wsgi_app = WhiteNoise(
#     app.wsgi_app,
#     root=os.path.join(os.path.dirname(__file__), "staticfiles"),
#     prefix="assets/",
#     max_age=WHITENOISE_MAX_AGE,
# )


#from flask_sqlalchemy import SQLAlchemy
#from sqlalchemy import create_engine
#from sqlalchemy.orm import sessionmaker
#from web.project.database_setup2 import Base, tracker


# Set the secret key to some random bytes. Keep this really secret!
#app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'
session = db.session

# Connect to Database and create database session
#db = SQLAlchemy(app)
#engine = create_engine('sqlite:///vi-tracker.db')

#Base.metadata.bind = engine
#DBSession = sessionmaker(bind=engine)
#session = DBSession()

app.config["MEDIA_FOLDER"] = os.path.join(os.path.dirname(__file__), "static")
app.config["ALLOWED_FILE_EXTENSIONS"] = ['NPY', 'FITS', 'CVS']
app.config["MAX_FILE_FILESIZE"] = 0.2 * 1024 * 1024

@app.template_global()
def static_url(prefix, filename):
    return urljoin(app.config["STATIC_URL"], f"{prefix}/{filename}")

@app.route("/staticfiles/<path:filename>")
def mediafiles(filename):
    return send_from_directory(app.config["MEDIA_FOLDER"], filename)

@app.route('/')
@app.route('/home')
def home():

    pjs_open = session.query(tracker).filter_by(status='open', vi=True, author=True).all()
    pjs_closed = session.query(tracker).filter_by(status='closed', vi=True, author=True).all()
    pjs_nonVI = session.query(tracker).filter_by(vi=False, author=True).all()

    #update progress for each room
    for pjs in [pjs_open, pjs_closed]:
        for pj in pjs:
            progress = get_room_progress(pj_room=pj)
            pj.progress = progress
    #session.commit()
    session.close()

    return render_template('index.html', myprojects_open=pjs_open, myprojects_closed=pjs_closed, myprojects_nonVI=pjs_nonVI)


@app.route('/new_room/<int:id>', methods=['GET', 'POST'])
@app.route('/new_project/', methods=['GET', 'POST'])
def new_projects(id=None):

    if id is not None:
        try:
            pjs = session.query(tracker).filter_by(id=id).first()
            session.close()
            project = pjs.project
            email = pjs.email
            template = 'new_room.html'
        except:
            raise ValueError('No project with id %i' %(id))
    else:
        template = 'new_project.html'
        project = None

    file_info = {'file_cols':[]}

    if request.method == 'POST':

        if request.form.get('submit_file') == 'submit':

            file = request.files["file"]

            if file.filename == "":
                flash("No filename in file")
                return render_template(template, request=request, disabled=True, file_info=file_info, id=id, project=project)

            if allowed_file(file.filename):

                if id is not None:
                    ext = 'npy'
                    filename = secure_filename('%s_%s_%s.%s' % (project,
                                                request.form.get('room'),
                                                email,
                                                ext))

                else:
                    filename = get_filepath(request=request)

                file_path = os.path.join(app.config["MEDIA_FOLDER"], filename) #static_url('assets', filename=filename)
                #

                # If file exist, remove it
                # Handle errors while calling os.remove()
                try:
                    os.remove(file_path)
                except:
                    print("Error while deleting file %s or it does not exist." %(file_path))


                print(file_path)
                file.save(file_path)
                print("File saved")

                file_info = get_file_info(file_path, filename)

                return render_template(template, request=request, disabled=False, file_info=file_info, id=id, project=project)

            else:
                flash("That file extension is not allowed. Allowed extensions are %s" %(app.config["ALLOWED_FILE_EXTENSIONS"].join(' ')))
                return render_template(template, request=request, disabled=True, file_info=file_info, id=id, project=project)


        if request.form.get('make_gall') == 'continue':

            #create input data dict based on request
            req = {}

            if id is not None:
                ext = 'npy'
                filename = secure_filename('%s_%s_%s.%s' % (project,
                                            request.form.get('room'),
                                            email,
                                            ext))

            else:
                filename = get_filepath(request=request)

            file_path = os.path.join(app.config["MEDIA_FOLDER"], filename) #static_url('assets', filename=filename)
            #
            data = np.load(file_path)

            #create project directory root
            if id is None:
                #don't forget the author details
                for key in ['name', 'afilliation', 'email', 'project', 'project_description']:
                    req[key] = request.form.get(key)

            else:
                project_details = {'name':pjs.name, 'afilliation':pjs.afilliation, 'email':pjs.email, 'project':pjs.project, 'project_description':pjs.project_description}
                for key, value in zip(project_details.keys(), project_details.values()):
                    req[key] = value

            req['room'] = request.form.get('room')

            if request.form.get('centres') == 'ALL':
                idx = list(np.where(np.ones_like(data, dtype=bool)))[0]
            else:
                idx = list(np.where(data[request.form.get('centres')]))[0]

            random.shuffle(idx)

            if len(idx) < int(request.form.get('VIrequest')):
                flash('VI Requested larger than available sample. Maximum is %i' %(len(idx)))

                return render_template(template, request=request, disabled=False, file_info=file_info, id=id, project=project)

            #req['ncols'] = int(request.form.get('Ncols')) #number of columns in gallery grid #incorporate to html
            req['vi_req'] = int(request.form.get('VIrequest'))
            req['batchsize'] = int(request.form.get('BatchSize'))
            req['boxsize'] = int(request.form.get('BoxSize'))
            module_Nbatchs = int(req['vi_req']//req['batchsize'])

            if req['vi_req'] > req['batchsize']:
                batchs_idx = idx[:module_Nbatchs * req['batchsize']].reshape(module_Nbatchs, req['batchsize']).tolist()
                if req['vi_req'] / module_Nbatchs * req['batchsize'] > 1:
                    batchs_idx.append(idx[module_Nbatchs * req['batchsize']:req['vi_req']].tolist())
            else:
                batchs_idx = idx[:req['vi_req']].reshape(1, req['vi_req']).tolist()

            req['nbatchs'] = len(batchs_idx)
            req['ncentres'] = len(idx)
            req['ndata'] = len(data)

            _batchs_idx = {}
            for num, i in enumerate(batchs_idx):
                _batchs_idx['%i' %(num)] = np.array(i)
            req['batchs_idx'] = _batchs_idx
            req['coord_names'] = [request.form.get('RA'), request.form.get('DEC')]

            if (len(request.form.getlist('label_col')) < 2) & ('None' in request.form.getlist('label_col')):
                req['labels'] = None
            else:
                req['labels'] = {key:val for key, val in zip(request.form.getlist('label_name'), request.form.getlist('label_col'))}

            if (len(request.form.getlist('info_col')) < 2) & ('None' in request.form.getlist('info_col')):
                req['info_list'] = None
            else:
                req['info_list'] = {key:val for key, val in zip(request.form.getlist('info_name')+['RA', 'DEC'], request.form.getlist('info_col')+req['coord_names'])}


            layers = []
            for i in request.form.getlist('layers'):
                layers.append('%s-resid' %(i))
                layers.append('%s-model' %(i))
                layers.append('%s' %(i))

            req['layers'] = layers
            req['centres'] = request.form.get('centres')
            unclassified_label = ['UNCL']

            if (len(request.form.getlist('VIlabels')) < 2) & ('' in request.form.getlist('VIlabels')):
                req['vi_labels'] = None
                VI = False
            else:
                req['vi_labels'] = request.form.getlist('VIlabels') + unclassified_label
                VI = True

            req['vi'] = VI

            # Get elements of batchs_idx
            idxs = [item for sublist in batchs_idx for item in sublist]

            req['vi_query'] = {key:unclassified_label[0] for key in idxs}

            _plots = {}
            for num, i in enumerate(batchs_idx):

                _plots['%i' %(num)] = []

            req['plots'] = _plots


            # Add new entry to database
            newentry = tracker(project=req['project'],
                               room=req['room'],
                               name=req['name'],
                               afilliation=req['afilliation'],
                               email=req['email'],
                               progress=int(0),
                               status='open',
                               author=True,
                               vi=req['vi'],
                               vi_req=req['vi_req'],
                               project_description=req['project_description'],
                               #ncols=req['ncols'],
                               batchsize=req['batchsize'],
                               boxsize=req['boxsize'],
                               nbatchs=req['nbatchs'],
                               ncentres=req['ncentres'],
                               batchs_idx=req['batchs_idx'],
                               ndata=req['ndata'],
                               coord_names=req['coord_names'],
                               labels=req['labels'],
                               info_list=req['info_list'],
                               layers=req['layers'],
                               centres=req['centres'],
                               vi_labels=req['vi_labels'],
                               #plots=req['plots'],
                               vi_query=req['vi_query']
                               )
            session.add(newentry)
            session.commit()
            session.close()


            batchID = 0

            pj = session.query(tracker).filter_by(project=req['project'], room=req['room'], email=req['email'], author=True).first()

            if pj:
                return redirect(url_for('progress', room_id=pj.id, filename=filename, batch=0))
            else:
                raise ValueError('Project does not exist.')

    else:
        return render_template(template, disabled=True, file_info=file_info, id=id, project=project)

@app.route('/progress/<int:room_id>/<filename>/<batch>')
def progress(room_id, filename, batch):

    pj = session.query(tracker).filter_by(id=room_id, author=True).first()

    print('================ A ==============')

    if pj:

        file_path = os.path.join(app.config["MEDIA_FOLDER"], filename)
        data = np.load(file_path)
        batch = int(batch)

        if pj.labels is not None:
            veto = {key:data[val] for key, val in zip(pj.labels.keys(), pj.labels.values())}
        else:
            veto = None

        if pj.info_list is not None:
            info = {key:data[val] for key, val in zip(pj.info_list.keys(), pj.info_list.values())}
        else:
            info = None

        coord = [data[i] for i in pj.coord_names]

        #_plots = pj.plots

        plots = html_postages(coord=coord, idx=pj.batchs_idx[str(batch)], veto=veto, info=info, layer_list=pj.layers, BoxSize=pj.boxsize)
        #_plots['%s' %str(batch)] = plots
        #pj.update({'plots': _plots})
        if batch == 0:
            pj.plots = {'0':plots}
        else:
            current_plots = {'%i' %(batch):plots}
            pj.plots = {**pj.plots, **current_plots}
        #pj.plots = {key:val for key, val in zip(_plots.keys(), _plots.values())}
        session.commit()
        print('================ progress ==============')
        print('Batch %i created...' %(batch))
        #print(pj.plots)
        #print(_plots[str(batch)])


        if batch < (pj.nbatchs - 1):
            session.close()
            return redirect(url_for('progress', room_id=room_id, filename=filename, batch=batch+1))
        else:
            session.close()
            return redirect(url_for('create_entry', id=pj.id, name=pj.name, afilliation=pj.afilliation,
                                        email=pj.email, batchID=0))

    else:
        print('================ B ==============')
        raise ValueError('Project does not exist.')

# @app.route("/jobs/<job_key>", methods=['GET'])
# def get_results(job_key):
#
#     job = Job.fetch(job_key, connection=conn)
#
#     if job.is_finished:
#         return str(job.result), 200
#     else:
#         return "Nay!", 202


@app.route('/create_entry/<int:id>/<name>/<afilliation>/<email>/<int:batchID>')
def create_entry(id, name, afilliation, email, batchID):

    room_id, entry_id, batchID = create_joiners_entry(id=id, name=name, afilliation=afilliation, email=email, batchID=batchID)

    return redirect(url_for('viewer', _external=True, room_id=room_id, entry_id=entry_id, batchID=batchID))


@app.route('/viewer/<int:room_id>/<int:entry_id>/<int:batchID>', methods=['GET', 'POST'])
def viewer(room_id, entry_id=None, batchID=None):

    pj_room = session.query(tracker).filter_by(id=room_id).first()
    if not pj_room:
        raise ValueError('No room with ID %i was found.' %(room_id))

    if entry_id == int(999):
        pj_entry = None
    else:
        pj_entry = session.query(tracker).filter_by(id=entry_id).one()

        if not pj_entry:
            raise ValueError('No entry with ID %i was found.' %(entry_id))

    if request.method == 'POST':

        if request.form.get('dashboard') == 'continue':

            return redirect(url_for('user_active_rooms', user=pj_entry.email))

        if request.form.get('next') == 'continue':

            batchID = int(999)

            return redirect(url_for('create_entry', id=pj_room.id, name=pj_entry.name, afilliation=pj_entry.afilliation, email=pj_entry.email, batchID=batchID))

        if request.form.get('save') == 'continue':

            vi_query = {}

            for key in request.form:
                if key.startswith('class.'):
                    id_ = key.partition('.')[-1]
                    value = request.form[key]
                    vi_query[int(id_)] = value
            try:
                pj_entry.vi_query = vi_query
                session.commit()
                flash('Entries saved successfully')
            except:
                raise ValueError('Error occurred when trying to save VI entries.')

    plot_dict = pj_room.plots[str(batchID)]

    return render_template('room.html', pj_room=pj_room, pj_entry=pj_entry, batchID=batchID, plot_dict=plot_dict)
    #return encode_utf8(html)

@app.route('/join/<int:room_id>/', methods=['GET', 'POST'])
def join(room_id):

    pj_room = session.query(tracker).filter_by(id=room_id).first()

    if not pj_room:
        flash('Something went wrong. No room with ID %i was found.' %(room_id))
        return redirect(url_for('home'))

    session.close()

    if request.method == 'POST':
        if request.form.get('make_gall') == 'continue':

            req = request.form
            name = req.get('name')
            email = req.get('email')
            afilliation = req.get('afilliation')

            return redirect(url_for('create_entry', id=room_id, name=name, afilliation=afilliation, email=email, batchID=int(999)))

    return render_template('join.html', button='Go to galleries', pj_room=pj_room, join=True)

@app.route('/resume', methods=['GET', 'POST'])
def resume():

    if request.method == 'POST':
        if request.form.get('make_gall') == 'continue':

            req = request.form
            email = req.get('email')

            pjs = session.query(tracker).filter_by(email=email).all()
            session.close()

            if pjs:
                return redirect(url_for('user_active_rooms', _external=True, user=email))
            else:
                text = '%s does not have active rooms yet. Go to Projects to join an existing room.' %(email)
                flash(text)
                return render_template('join.html', button='Continue', join=False)

    return render_template('join.html', button='Continue', join=False)

@app.route('/current_rooms/<user>')
def user_active_rooms(user):

    pjs = session.query(tracker).filter_by(email=user).all()
    pj_entry = session.query(tracker).filter_by(email=user, author=False).all()
    pj_room = session.query(tracker).filter_by(email=user, author=True).all()

    if not pjs:
        session.close()
        flash('You do not have projects yet, neither VI works in process.')
        return render_template('join.html', button='Continue', join=False)

    if len(pj_entry) > 0:
        for pj in pj_entry:
            progress = get_user_progress(pj_entry=pj)
            pj.progress = progress

        name = pj_entry[0].name

    if pj_room:
        name = pj_room[0].name

    myprojects_open = session.query(tracker).filter_by(email=user, status='open', vi=True, author=True).all()
    myprojects_closed = session.query(tracker).filter_by(email=user, status='closed', vi=True, author=True).all()
    myprojects_nonVI = session.query(tracker).filter_by(email=user, vi=False, author=True).all()

    for myprojects in [myprojects_open, myprojects_closed]:
        for pj in myprojects:
            progress = get_room_progress(pj_room=pj)
            pj.progress = progress

    session.close()

    return render_template('user_active_rooms.html', rooms=pj_entry, myprojects_open=myprojects_open,
                           myprojects_closed=myprojects_closed, myprojects_nonVI=myprojects_nonVI,
                           name=name, user=user)

# This will let us Delete our book
@app.route('/delete/<int:room_id>/<email>', methods=['GET', 'POST'])
def delete(room_id, email):

    pj_room = session.query(tracker).filter_by(id=room_id, author=True).first()

    if not pj_room:

        session.close()
        flash('Something went wrong. No room with ID %i was found.' %(room_id))
        return redirect(url_for('user_active_rooms', user=email))

    room = pj_room.room

    # Remove file

    filename = '%s_%s_%s.%s' % (pj_room.project, pj_room.room, pj_room.email, 'npy')
    file_path = os.path.join(app.config["MEDIA_FOLDER"], filename)

    try:
        shutil.rmtree(file_path)
    except OSError as e:
        print("Error: %s : %s" % (file_path, e.strerror))

    # Remove all the entries that depends on this room
    pjs = session.query(tracker).filter_by(room_id=room_id, author=False).all()

    if pjs:
        for pj in pjs:
            session.delete(pj)
            session.commit()

    # Remove room
    session.delete(pj_room)
    session.commit()

    session.close()

    flash("Room %s Deleted Successfully" %(room))
    return redirect(url_for('user_active_rooms', user=email))


@app.route('/<action>/<int:room_id>/<email>', methods=['GET', 'POST'])
def closed_open(room_id, action, email):

    pj_room = session.query(tracker).filter_by(id=room_id, author=True).first()

    if not pj_room:

        session.close()
        flash('Something went wrong. No room with ID %i was found.' %(room_id))
        return redirect(url_for('user_active_rooms', user=email))

    room = pj_room.room

    # Close room
    pj_room.status = action
    session.commit()

    # Close entries
    pjs = session.query(tracker).filter_by(room_id=room_id, author=False).all()

    if pjs:
        for pj in pjs:
            pj.status = action
            session.commit()

    session.close()

    flash('You have successfully %s Room %s' %(action, room))
    return redirect(url_for('user_active_rooms', user=email))

@app.route('/download/<int:room_id>')
def download_file(room_id):

    pjs = session.query(tracker).filter_by(room_id=room_id, author=False).all()
    pj_room = session.query(tracker).filter_by(id=room_id, author=True).first()

    if not pjs:
        session.close()
        flash('There is no data to download yet.')
        return redirect(url_for('home'))

    results = {}
    results['idx'] = list(pj_room.vi_query.keys())

    users = [pj.email for pj in pjs]
    for user in set(users):
        pj_user = session.query(tracker).filter_by(room_id=room_id, author=False, email=user).all()
        output = pj_room.vi_query
        for pj in pj_user:
            for key, value in zip(pj.vi_query.keys(), pj.vi_query.values()):
                if value != 'UNCL':
                    output[key] = value
        results[user] = list(output.values())

    session.close()

    file_path = os.path.join(app.config["MEDIA_FOLDER"], 'results_%s_%s_%i.csv' %(pj_room.project, pj_room.room, pj_room.id))

    try:
        os.remove(file_path)
    except:
        print("file %s does not exist. " % (file_path))

    pd.DataFrame(results).to_csv(file_path, sep='\t', index=False)

    return send_file(file_path, as_attachment=True)


#==============================
#Some defs
#==============================

def get_file_info(file_path, filename):

    ext = filename.rsplit(".", 1)[1]
    file_info = {}
    if ext.upper() == 'NPY':
        data = np.load(file_path)
        file_cols = data.dtype.names
        file_info['file_cols'] = file_cols
        file_info['array_size'] = len(data)
        for col in file_cols:
            if data[col].dtype == 'bool':
                file_info['%s_sum' %(col)] = np.sum(data[col])

        return file_info

def get_filepath(request):

    # Check require info exist in form
    for key in ['project', 'room', 'email']:
        try:
            request.form.get(key)
        except:
            raise ValueError('No %s in form' %(key))

    ext = 'npy' #secure_filename(filename).rsplit(".", 1)[1]
    filename = secure_filename('%s_%s_%s.%s' % (request.form.get('project'),
                                                request.form.get('room'),
                                                request.form.get('email'),
                                                ext))

    return filename


def create_joiners_entry(id=None, name=None, afilliation=None, email=None, batchID=None):

    pj = session.query(tracker).filter_by(id=id).first()

    if pj:

        if (pj.vi) and (pj.status == 'open'):

            if (batchID is None) or (batchID == 999):
                print('Assign free batchID...')
                batchID = find_batch_available(room_id=id, email=email)

            _pj = session.query(tracker).filter_by(room_id=id, email=email, batch=batchID).first()
            if _pj:
                print('Entry already exists.')
                return id, _pj.id, batchID

            # Add new entry to database
            print(name, afilliation, email, batchID)
            newentry = tracker(project=pj.project,
                               room=pj.room,
                               name=name,
                               afilliation=afilliation,
                               email=email,
                               progress=int(0),
                               status='open',
                               author=False,
                               batch=batchID,
                               room_id=id,
                               vi_query=pj.vi_query
                                )

            session.add(newentry)
            session.commit()
            session.close()

            _pj = session.query(tracker).filter_by(room_id=id, email=email, batch=batchID).first()
            if _pj:
                print('Entry created successfully.')
                return id, _pj.id, batchID
            else:
                raise ValueError('No entry found.')

        else:
            print('Room is non-VI. No entry saved.')
            return id, int(999), batchID

    else:
        raise ValueError('Project with ID %i does not exist.' % (id))


def encode_utf8(u):
    ''' Encode a UTF-8 string to a sequence of bytes.

    Args:
        u (str) : the string to encode

    Returns:
        bytes

    '''
    import sys
    if sys.version_info[0] == 2:
        u = u.encode('utf-8')
    return u



def allowed_file(filename):

    if not "." in filename:
        return False

    ext = filename.rsplit(".", 1)[1]

    if ext.upper() in app.config["ALLOWED_FILE_EXTENSIONS"]:
        return True
    else:
        return False


def allowed_file_filesize(filesize):

    if int(filesize) <= app.config["MAX_FILE_FILESIZE"]:
        return True
    else:
        return False

def find_batch_available(room_id, email):

    pjs = session.query(tracker).filter_by(room_id=room_id, author=False).all()
    pj_room = session.query(tracker).filter_by(id=room_id, author=True).one()

    batchs_in_use = []
    for pj in pjs:
        batchs_in_use.append(pj.batch)

    for i in range(pj_room.nbatchs):
        if i in batchs_in_use:
            batchID = None
        else:
            batchID = i
            break

    if batchID is None:
        batchs_in_use = []
        pjs = session.query(tracker).filter_by(room_id=room_id, author=False, email=email).all()
        for pj in pjs:
            batchs_in_use.append(pj.batch)

        for i in range(pj_room.nbatchs):
            if i in batchs_in_use:
                batchID = None
            else:
                batchID = i
                break

    if batchID is None:
        batchID = 0

    session.close()

    return batchID


def get_room_progress(pj_room):

    pjs = session.query(tracker).filter_by(room_id=pj_room.id, author=False).all()
    N = 0
    for pj in pjs:
        N += int(np.sum(np.array(list(pj.vi_query.values())) != 'UNCL'))

    return np.round(100*N/pj_room.vi_req, 1)

def get_user_progress(pj_entry):

    pj_room = session.query(tracker).filter_by(id=pj_entry.room_id, author=True).first()
    tot = len(pj_room.batchs_idx[str(pj_entry.batch)])
    current = int(np.sum(np.array(list(pj_entry.vi_query.values())) != 'UNCL'))

    if tot == 0:
        tot = 1

    return np.round(100*current/tot, 1)


# function to return key for any value in a dict
def get_key(my_dict, val):
    for key, value in my_dict.items():
         if val == value:
             return key

    return "key doesn't exist"



if __name__ == '__main__':
    app.run()
#     HOST = '0.0.0.0'
#     PORT = 5000
#     app.run(HOST, PORT, debug=True)
