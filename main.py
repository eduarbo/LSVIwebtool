import glob
import os
import atexit
import random
import shutil
import subprocess
from zipfile import ZipFile

import pandas as pd

import numpy as np
from bokeh.client import pull_session
from flask import Flask, redirect, url_for, render_template, request, flash, send_file
from bokeh.embed.server import server_document
from werkzeug.utils import secure_filename

app = Flask(__name__)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database_setup import Base_tracker, Base_projects, tracker, VIprojects

# Set the secret key to some random bytes. Keep this really secret!
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'

# Connect to Database and create database session
engine_tracker = create_engine('sqlite:///vi-tracker.db')
engine_projects = create_engine('sqlite:///vi-projects.db')
Base_tracker.metadata.bind = engine_tracker
Base_projects.metadata.bind = engine_projects
DBSession_tracker = sessionmaker(bind=engine_tracker)
DBSession_projects = sessionmaker(bind=engine_projects)
session_tracker = DBSession_tracker()
session_projects = DBSession_projects()

app.config["FILE_UPLOADS"] = os.path.join(os.getcwd(), 'data_tmp')
app.config["ALLOWED_FILE_EXTENSIONS"] = ['NPY', 'FITS', 'CVS']
app.config["MAX_FILE_FILESIZE"] = 0.2 * 1024 * 1024

# bokeh_process = subprocess.Popen(
#     ['python', '-m', 'bokeh', 'serve', '--port 5006', '--allow-websocket-origin="*"', 'script.py'], stdout=subprocess.PIPE)
#
# @atexit.register
# def kill_server():
#     bokeh_process.kill()

@app.route('/')
@app.route('/home')
def home():

    pjs_open = session_projects.query(VIprojects).filter_by(status='open', VI=True).all()
    pjs_closed = session_projects.query(VIprojects).filter_by(status='closed', VI=True).all()
    pjs_nonVI = session_projects.query(VIprojects).filter_by(VI=False).all()

    #update progress for each room
    for pjs in [pjs_open, pjs_closed]:
        for pj in pjs:
            progress = get_room_progress(ProjectName=pj.project, RoomName=pj.room, VIreq=pj.VIreq)
            pj.progress = progress
    session_projects.close()

    return render_template('index.html', myprojects_open=pjs_open, myprojects_closed=pjs_closed, myprojects_nonVI=pjs_nonVI)

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



@app.route('/new_room/<int:id>', methods=['GET', 'POST'])
@app.route('/new_project/', methods=['GET', 'POST'])
def new_projects(id=None):

    print('=========== id =========')
    print(id)

    if id is not None:
        pjs = session_projects.query(VIprojects).filter_by(id=id).all()
        session_projects.close()
        project = pjs[0].project
        template = 'new_room.html'
    else:
        template = 'new_project.html'
        project = None

    file_info = {'file_cols':[]}

    if request.method == 'POST':

        #if request.files:
        if request.form.get('submit_file') == 'submit':

            file = request.files["file"]
            print('FILE:',file)

            if file.filename == "":
                print("No filename")
                return render_template(template, request=request, disabled=True, file_info=file_info, id=id, project=project)

            if allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config["FILE_UPLOADS"], filename)

                file.save(file_path)
                print("Image saved")

                file_info = get_file_info(file_path, filename)

                # Handle errors while calling os.remove()
                try:
                    os.remove(file_path)
                except:
                    print("Error while deleting file ", file_path)

                return render_template(template, request=request, disabled=False, file_info=file_info, id=id, project=project)

            else:
                print("That file extension is not allowed")
                return render_template(template, request=request, disabled=True, file_info=file_info, id=id, project=project)


        if request.form.get('make_gall') == 'continue':

            #create input data dict based on request
            req = {}
            req['room'] = request.form.get('room')
            #create project directory root
            if id is None:
                #don't forget the author details
                for key in ['name', 'afilliation', 'email', 'project', 'project_description']:
                    req[key] = request.form.get(key)

                room_path = os.path.join(os.getcwd(), 'projects', request.form.get('project'), request.form.get('room'))
                #proj_path = os.path.join(os.getcwd(), 'projects', request.form.get('project'))
            else:
                project_details = {'name':pjs[0].name, 'afilliation':pjs[0].afilliation, 'email':pjs[0].email, 'project':pjs[0].project, 'project_description':pjs[0].project_description}
                for key, value in zip(project_details.keys(), project_details.values()):
                    req[key] = value

                room_path = os.path.join(os.getcwd(), 'projects', pjs[0].project, req.get('room'))

            os.makedirs(room_path, exist_ok=True)

            #get file and save it to rooms path
            file = request.files["file"]
            #here an intermediate step to convert file to .npy
            file_path = os.path.join(room_path, 'file.npy')
            print('==========')
            print(file_path)
            file.save(file_path)

            data = np.load(file_path)

            if request.form.get('centres') == 'ALL':
                idx = list(np.where(np.ones_like(data, dtype=bool)))[0]
            else:
                idx = list(np.where(data[request.form.get('centres')]))[0]

            random.shuffle(idx)

            if len(idx) < int(request.form.get('VIrequest')):
                flash('VI Requested larger than sample. Maximum is %i' %(len(idx)))

                try:
                    shutil.rmtree(room_path)
                except OSError as e:
                    print("Error: %s : %s" % (room_path, e.strerror))

                return render_template(template, request=request, disabled=False, file_info=file_info, id=id, project=project)

            req['Ncols'] = int(request.form.get('Ncols')) #number of columns in gallery grid #incorporate to html
            req['VIrequest'] = int(request.form.get('VIrequest'))
            req['BatchSize'] = int(request.form.get('BatchSize'))
            req['BoxSize'] = int(request.form.get('BoxSize'))
            module_Nbatchs = int(req['VIrequest']//req['BatchSize'])

            if req['VIrequest'] > req['BatchSize']:
                idxs = idx[:module_Nbatchs * req['BatchSize']].reshape(module_Nbatchs, req['BatchSize']).tolist()
                if req['VIrequest'] / module_Nbatchs * req['BatchSize'] > 1:
                    idxs.append(idx[module_Nbatchs * req['BatchSize']:req['VIrequest']].tolist())
            else:
                idxs = idx[:req['VIrequest']].reshape(1, req['VIrequest']).tolist()

            req['Nbatchs'] = len(idxs)
            req['Ncentres'] = len(idx)

            for num, i in enumerate(idxs):
                req['%s_%s' %(request.form.get('room'), str(num))] = np.array(i)
            req['%s_Ndata' %(request.form.get('room'))] = len(data)

            #input params for viewer

            req['catpath'] = file_path
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

            req['layer_list'] = layers
            req['centre'] = request.form.get('centres')

            if (len(request.form.getlist('VIlabels')) < 2) & ('' in request.form.getlist('VIlabels')):
                req['RGlabels'] = None
                VI = False
            else:
                req['RGlabels'] = request.form.getlist('VIlabels')
                VI = True

            req['VI'] = VI

            #save dict in room directory
            np.save(os.path.join(room_path, 'requests'), req)

            for key in req.keys():
                print('%s: \t %s' %(key, req[key]))

            #Export user details of project and room and batchID to database
            batchID = 0 #assign first batchID

            #add entry to tracker's database only if project is VI
            if VI:
                newentry = tracker(project=req.get('project'), room=req.get('room'), batch=batchID,
                                    name=req.get('name'), afilliation=req.get('afilliation'), email=req.get('email'),
                                        progress=int(0), status='open')
                session_tracker.add(newentry)
                session_tracker.commit()

            #add entry to projects database for each room
            newentry = VIprojects(project=req.get('project'), project_description=req.get('project_description'), room=req.get('room'),
                                    name=req.get('name'), afilliation=req.get('afilliation'), email=req.get('email'),
                                        VIreq=req.get('VIrequest'), progress=int(0), status='open', VI=VI)
            session_projects.add(newentry)
            session_projects.commit()

            return redirect(url_for('viewer', ProjectName=req.get('project'), RoomName=req.get('room'), user=req.get('email'), batchID=batchID))
            #return render_template('new_project.html', request=request, disabled=False, file_info=file_info)
    else:
        return render_template(template, disabled=True, file_info=file_info, id=id, project=project)


#galleries page
@app.route('/<ProjectName>/<RoomName>/<user>/<int:batchID>', methods=['GET', 'POST'])
def viewer(ProjectName, RoomName, user, batchID):

    pjs = session_projects.query(VIprojects).filter_by(project=ProjectName, room=RoomName).one()
    session_projects.close()
    print('======== pjs ========')
    print(pjs.status)

    if request.form.get('next') == 'continue':

        #print('===== HERE ======')

        batchID = find_batch_available(ProjectName, RoomName, user) #assign batchID based on availability
        pathdir = os.path.join(os.getcwd(), 'projects', ProjectName, RoomName)
        userfile_path = '%s/%s_%s' %(pathdir, user, str(batchID))
        userfile_path_csv = '%s.csv' %(userfile_path)
        #print(batchID, userfile_path_csv)

        if os.path.isfile(userfile_path_csv):
            #print('========= enter ===========')
            reqPath = os.path.join(os.getcwd(), 'projects', ProjectName, RoomName, 'requests.npy')
            req = np.load(reqPath, allow_pickle=True).item()

            args = {}
            args['batchID'] = batchID
            args['reqPath'] = reqPath
            args['userfile_path'] = userfile_path
            flash('Hmmm, seems you have ran out of batchs in this room. You will be redirect to batch %i and continue where you left.' %(batchID+1))

            bokeh_script = server_document(url='http://localhost:5006/script', arguments=args)
            return render_template('room.html', bokeh_script=bokeh_script, template="Flask", current_batch=batchID, user=user, req=req, pjs=pjs)

        else:
            usr = session_tracker.query(tracker).filter_by(email=user).all()
            session_tracker.close()
            #add entry to database
            newentry = tracker(project=ProjectName, room=RoomName, batch=batchID,
                             name=usr[0].name, afilliation=usr[0].afilliation, email=usr[0].email, progress=int(0), status='open')
            session_tracker.add(newentry)
            session_tracker.commit()
            session_tracker.close()

            return redirect(url_for('viewer', ProjectName=ProjectName, RoomName=RoomName, user=user, batchID=batchID))


    reqPath = os.path.join(os.getcwd(), 'projects', ProjectName, RoomName, 'requests.npy')
    req = np.load(reqPath, allow_pickle=True).item()
    userfile_path = os.path.join(os.getcwd(), 'projects', ProjectName, RoomName, '%s_%s' %(user, str(batchID)))
    userfile_path_csv = '%s.csv' %(userfile_path)

    idx = req.get('%s_%s' %(RoomName, str(batchID)))
    Nbatchs = req['Nbatchs']

    args = {}
    args['batchID'] = batchID
    args['reqPath'] = reqPath

    if (req.get('RGlabels') is not None) & (pjs.status == 'open'):

        print('===== inside ====')

        if not os.path.isfile(userfile_path_csv) :

            #create selections file
            pddata = {'data':np.full(req.get('%s_Ndata' %(RoomName)), 'NA', dtype='S4')}
            selections = pd.DataFrame(pddata, columns=["data"])
            unclassified_label = ['UNCL']

            #get centres from batchID
            selections.iloc[idx] = unclassified_label[0]
            selections.to_csv('%s.csv' %(userfile_path), index=False)

            #If user not in database, create entry for that user
            try:
                session_tracker.query(tracker).filter_by(project=ProjectName, room=RoomName, batch=batchID, email=user).one()
            except:
                usr = session_tracker.query(tracker).filter_by(project=ProjectName, room=RoomName, email=user).all()
                print('Data entry does not exist. Creating new entry for this user')
                #add entry to database
                newentry = tracker(project=usr[0].project, room=usr[0].room, batch=batchID,
                                 name=usr[0].name, afilliation=usr[0].afilliation, email=usr[0].email, progress=int(0), status='open')
                session_tracker.add(newentry)
                session_tracker.commit()
                session_tracker.close()

        args['userfile_path'] = userfile_path
        bokeh_script = server_document(url='http://localhost:5006/script', arguments=args)
        return render_template('room.html', bokeh_script=bokeh_script, template="Flask", current_batch=batchID, user=user, req=req, pjs=pjs)

    else:

        args['userfile_path'] = None
        bokeh_script = server_document(url='http://localhost:5006/script', arguments=args)
        return render_template('room.html', bokeh_script=bokeh_script, template="Flask", current_batch=batchID, user=user, req=req, pjs=pjs)

#/
#
# @app.route('/next_available/<project>/<room>/<user>', methods=['GET', 'POST'])
# def next_available(project, room, user):
#
#             #Export user details of project and room and batchID to database
#             batchID = find_batch_available(project, room, user) #assign batchID based on availability
#             pathdir = os.path.join(os.getcwd(), 'projects', project, room)
#             userfile_path = '%s%s_%s' %(pathdir, user, str(batchID))
#             userfile_path_csv = '%s.csv' %(userfile_path)
#
#             if os.path.isfile(userfile_path_csv):
#                 flash('Hmmm, seems you have ran out of batchs in this room. You will be redirect to batch %i and continue where you left.' %(batchID))
#                 return redirect(url_for('viewer', ProjectName=project, RoomName=room, user=user, batchID=batchID))
#             else:
#                 usr = session_tracker.query(tracker).filter_by(email=user).all()
#                 session_tracker.close()
#                 #add entry to database
#                 newentry = tracker(project=project, room=room, batch=batchID,
#                                  name=usr[0].name, afilliation=usr[0].afilliation, email=usr[0].email, progress=int(0), status='open')
#                 session_tracker.add(newentry)
#                 session_tracker.commit()
#                 session_tracker.close()
#
#                 return redirect(url_for('viewer', ProjectName=project, RoomName=room, user=user, batchID=batchID))


@app.route('/join/<ProjectName>/<RoomName>/', methods=['GET', 'POST'])
def join(ProjectName, RoomName):

    if request.method == 'POST':
        if request.form.get('make_gall') == 'continue':

            req = request.form
            name = req.get('name')
            email = req.get('email')
            afill = req.get('afilliation')
            user = email

            #Export user details of project and room and batchID to database
            batchID = find_batch_available(ProjectName, RoomName, user) #assign batchID based on availability
            pathdir = os.path.join(os.getcwd(), 'projects', ProjectName, RoomName)
            userfile_path = '%s/%s_%s' %(pathdir, user, str(batchID))
            #print(userfile_path)
            userfile_path_csv = '%s.csv' %(userfile_path)

            if os.path.isfile(userfile_path_csv):
                print('Hmmm, seems you have ran out of batchs in this room. You will be redirect to batch %i and continue where you left.' %(batchID))
                return redirect(url_for('viewer', ProjectName=ProjectName, RoomName=RoomName, user=user, batchID=batchID))
            else:
                #add entry to database
                newentry = tracker(project=ProjectName, room=RoomName, batch=batchID,
                                 name=name, afilliation=afill, email=email, progress=int(0), status='open')
                session_tracker.add(newentry)
                session_tracker.commit()
                session_tracker.close()

                return redirect(url_for('viewer', ProjectName=ProjectName, RoomName=RoomName, user=user, batchID=batchID))
    else:

        author = session_projects.query(VIprojects).filter_by(room=RoomName, project=ProjectName).one()
        text = 'By %s from %s' %(author.name, author.afilliation)
        session_projects.close()
        return render_template('join.html', button='Go to galleries', author=author, join=True)

@app.route('/resume', methods=['GET', 'POST'])
def resume():

    if request.method == 'POST':
        if request.form.get('make_gall') == 'continue':

            req = request.form
            email = req.get('email')

            usr = session_tracker.query(tracker).filter_by(email=email).all()
            session_tracker.close()
            pjs = session_projects.query(VIprojects).filter_by(email=email).all()
            session_projects.close()

            if (len(usr) > 0) or (len(pjs) > 0):
                return redirect(url_for('user_active_rooms', user=email))
            else:
                text = '%s does not have active rooms yet. Go to Projects to join an existing room.' %(email)
                flash(text)
                return render_template('join.html', button='Continue', join=False)

    return render_template('join.html', button='Continue', join=False)

@app.route('/current_rooms/<user>')
def user_active_rooms(user):

    rooms = session_tracker.query(tracker).filter_by(email=user).all()
    #username = user+'_'+rooms[0].afilliation

    print(user, rooms)

    if len(rooms) > 0:
        for room in rooms:
            progress = get_user_progress(ProjectName=room.project, RoomName=room.room,
                                       user=user, batchID=room.batch)
            room.progress = progress
        session_tracker.close()
        name = rooms[0].name
        print('======1=========')
        print(name)

    pjs = session_projects.query(VIprojects).filter_by(email=user).all()
    session_projects.close()
    if len(pjs) > 0:
        name = pjs[0].name
        print('======2=========')
        print(name)

    myprojects_open = session_projects.query(VIprojects).filter_by(email=user, status='open', VI=True).all()
    myprojects_closed = session_projects.query(VIprojects).filter_by(email=user, status='closed', VI=True).all()
    myprojects_nonVI = session_projects.query(VIprojects).filter_by(email=user, VI=False).all()

    for myprojects in [myprojects_open, myprojects_closed]:
        for pj in myprojects:
            progress = get_room_progress(ProjectName=pj.project, RoomName=pj.room, VIreq=pj.VIreq)
            pj.progress = progress

    session_projects.close()

    return render_template('user_active_rooms.html', rooms=rooms, myprojects_open=myprojects_open,
                           myprojects_closed=myprojects_closed, myprojects_nonVI=myprojects_nonVI,
                           name=name, user=user)

# This will let us Delete our book
@app.route('/delete/<ProjectName>/<RoomName>/<email>', methods=['GET', 'POST'])
def delete(ProjectName, RoomName, email):

    RoomToDelete = session_projects.query(VIprojects).filter_by(project=ProjectName, room=RoomName).one()
    session_projects.close()

    RoomToDelete_tracker = session_tracker.query(tracker).filter_by(project=ProjectName, room=RoomName).all()
    for room in RoomToDelete_tracker:
        session_tracker.delete(room)
        session_tracker.commit()
    session_tracker.close()

    pathdir = os.path.join(os.getcwd(), 'projects', ProjectName, RoomName)

    try:
        shutil.rmtree(pathdir)
    except OSError as e:
        print("Error: %s : %s" % (pathdir, e.strerror))

    #delete data from databases
    session_projects.delete(RoomToDelete)
    session_projects.commit()
    session_projects.close()

    #print('========================= = = = = = = ')
    rooms_left = session_projects.query(VIprojects).filter_by(project=ProjectName).all()
    session_projects.close()
    if len(rooms_left) < 1:
        pathdir_project = os.path.abspath(os.getcwd())+'/projects/%s/' %(ProjectName)
        try:
            shutil.rmtree(pathdir_project)
        except OSError as e:
            print("Error: %s : %s" % (pathdir_project, e.strerror))

    if len(session_projects.query(VIprojects).filter_by(email=email).all()) > 0:

        flash("Room %s Deleted Successfully" %(RoomName))
        return redirect(url_for('user_active_rooms', user=email))
    else:
        return redirect(url_for('home'))

@app.route('/<action>/<int:id>', methods=['GET', 'POST'])
def closed_open(id, action):

    room_to_close = session_projects.query(VIprojects).filter_by(id=id).one()

    print('========= Room to close ==============')
    print(room_to_close.status)
    room_to_close.status = action
    session_projects.commit()
    print(room_to_close.status)

    project = room_to_close.project
    room = room_to_close.room
    email = room_to_close.email
    session_projects.close()

    rooms_tracker = session_tracker.query(tracker).filter_by(project=project, room=room).all()
    for room in rooms_tracker:
        room.status = action
        session_tracker.commit()
    session_tracker.close()

    flash('You have successfully %s Room %s' %(action, room))
    return redirect(url_for('user_active_rooms', user=email))

@app.route('/download/<int:id>')
def download_file(id):

    pj = session_projects.query(VIprojects).filter_by(id=id).one()
    session_projects.close()

    room_path = os.path.join(os.getcwd(), 'projects', pj.project, pj.room)

    #merge results with targets file
    #
    room = pj.room
    project = pj.project
    author_name = pj.name
    author_afill = pj.afilliation

    reqPath = os.path.join(room_path, 'requests.npy')
    req = np.load(reqPath, allow_pickle=True).item()

    resdict = {}
    files = glob.glob("%s/*.csv" %(room_path))

    #
    idxs = []
    for i in range(req.get('Nbatchs')):
        idxs += list(req.get('%s_%i' %(room, i)))

    for file in files:

        resdict[os.path.basename(file[:-4])] = np.array(pd.read_csv(file))

    rescat = np.hstack(list(resdict.values()))
    outfile = np.full(len(np.load(os.path.join(room_path, 'file.npy'))), np.nan, dtype=object)

    for i in idxs:
        element = np.delete(rescat[i], np.where(rescat[i] == "b'NA'"))
        outfile[i] = [i for i in element]

    #create results dir
    os.makedirs(os.path.join(room_path, 'results'), exist_ok=True)

    #fmt='%.18e', delimiter=' ', newline='n', header='', footer='', comments='# ', encoding=None
    VIresults_file = '%s/results/VIresults_%s_%s_from_%s_at_%s.csv' %(room_path, project, room, author_name, author_afill)
    VIindexes_file = '%s/results/VIindexes_%s_%s_from_%s_at_%s.csv' %(room_path, project, room, author_name, author_afill)
    result_file = '%s/results/results_%s_%s_from_%s_at_%s.zip' %(room_path, project, room, author_name, author_afill)

    #remove existing files
    for file in [VIresults_file, VIindexes_file, result_file]:
        try:
            os.remove(file)
        except:
            print("no file %s in %s " %(file, os.path.join(room_path, 'results')))


    np.savetxt(VIresults_file, list(outfile), fmt="%s")
    np.savetxt(VIindexes_file, idxs, fmt='%i')

    with ZipFile(result_file, mode='w') as zf:
        for f in [VIresults_file, VIindexes_file]:
            zf.write(f)

    return send_file(result_file, as_attachment=True)


# @app.route('/uploader', methods = ['GET', 'POST'])
# def upload_file():
#     print('====== outside =============')
#     if request.method == 'POST':
#         if request.form.get('submit') == 'submit':
#             print('====== inside =============')
#             f = request.files['file']
#             f.save(secure_filename(f.filename))
#             return 'file %s uploaded successfully' %(f.filename)


#==============================
#Some defs
#==============================



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

def find_batch_available(ProjectName, RoomName, user):

    reqPath = os.path.join(os.getcwd(), 'projects', ProjectName, RoomName, 'requests.npy')
    req = np.load(reqPath, allow_pickle=True).item()
    Nbatchs = req.get('Nbatchs')

    pathdir = os.path.join(os.getcwd(), 'projects', ProjectName, RoomName)
    files = glob.glob("%s/*.csv" %(pathdir))

    batchs_in_use = []
    for file in files:
        batchs_in_use.append(int(file.split('_')[-1].split('.')[0]))

    for i in range(Nbatchs):
        if i in batchs_in_use:
            batchID = None
        else:
            batchID = i
            break

    if batchID is None:
        files = glob.glob("%s/%s*.csv" %(pathdir, user))
        batchs_in_use = []
        for file in files:
            batchs_in_use.append(int(file.split('_')[-1].split('.')[0]))

        for i in range(Nbatchs):
            if i in batchs_in_use:
                batchID = None
            else:
                batchID = i
                break


    if batchID is None:
        batchID = 0

    return batchID

def get_user_progress(ProjectName, RoomName, user, batchID):

    pathdir = os.path.join(os.getcwd(), 'projects', ProjectName, RoomName)
    file = "%s/%s_%i.csv" %(pathdir, user, batchID)

    reqPath = os.path.join(os.getcwd(), 'projects', ProjectName, RoomName, 'requests.npy')
    req = np.load(reqPath, allow_pickle=True).item()
    idxs = req.get('%s_%s' %(RoomName, str(batchID)))
    tot = len(idxs)

    progress = 0

    userfile = np.array(pd.read_csv(file)['data'], dtype=str)
    mask = (userfile != "b'NA'") & (userfile != 'UNCL')
    progress += int(np.sum(mask))

    return np.round(100*progress/tot, 1)

def get_room_progress(ProjectName, RoomName, VIreq):

    pathdir = os.path.join(os.getcwd(), 'projects', ProjectName, RoomName)
    files = glob.glob("%s/*.csv" %(pathdir))

    progress = 0

    for file in files:

        userfile = np.array(pd.read_csv(file)['data'], dtype=str)
        mask = (userfile != "b'NA'") & (userfile != 'UNCL')
        progress += int(np.sum(mask))

    return np.round(100*progress/VIreq, 1)


# function to return key for any value in a dict
def get_key(my_dict, val):
    for key, value in my_dict.items():
         if val == value:
             return key

    return "key doesn't exist"


if __name__ == '__main__':
    HOST = '0.0.0.0'
    PORT = 5000
    app.run(HOST, PORT, debug=True)
