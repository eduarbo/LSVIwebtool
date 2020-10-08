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
from bokeh.embed import components, autoload_static
from bokeh.resources import CDN
from flask import Flask, redirect, url_for, render_template, request, flash, send_file
from bokeh.embed.server import server_document
from werkzeug.utils import secure_filename

app = Flask(__name__)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database_setup import Base, tracker

from lscutout import html_postages

# Set the secret key to some random bytes. Keep this really secret!
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'

# Connect to Database and create database session
engine = create_engine('sqlite:///vi-tracker.db')

Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
session = DBSession()

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

    print('=========== id =========')
    print(id)

    if id is not None:
        try:
            pjs = session.query(tracker).filter_by(id=id).one()
            session.close()
            project = pjs.project
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
            print('FILE:',file)

            if file.filename == "":
                flash("No filename in file")
                return render_template(template, request=request, disabled=True, file_info=file_info, id=id, project=project)

            if allowed_file(file.filename):

                filename = get_filepath(request=request)
                file_path = os.path.join(app.config["FILE_UPLOADS"], filename)

                # If file exist, remove it
                # Handle errors while calling os.remove()
                try:
                    os.remove(file_path)
                except:
                    print("Error while deleting file %s or it does not exist." %(file_path))

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
            filename = get_filepath(request=request)
            file_path = os.path.join(app.config["FILE_UPLOADS"], filename)
            print('===== FP =====')
            print(file_path)
            #file.save(file_path)
            data = np.load(file_path)

            #create project directory root
            if id is None:
                #don't forget the author details
                for key in ['name', 'afilliation', 'email', 'project', 'project_description']:
                    req[key] = request.form.get(key)

                #room_path = os.path.join(os.getcwd(), 'projects', request.form.get('project'), request.form.get('room'))
                #proj_path = os.path.join(os.getcwd(), 'projects', request.form.get('project'))
            else:
                project_details = {'name':pjs[0].name, 'afilliation':pjs[0].afilliation, 'email':pjs[0].email, 'project':pjs[0].project, 'project_description':pjs[0].project_description}
                for key, value in zip(project_details.keys(), project_details.values()):
                    req[key] = value

                #room_path = os.path.join(os.getcwd(), 'projects', pjs[0].project, request.form.get('room'))

            req['room'] = request.form.get('room')
            #os.makedirs(room_path, exist_ok=True)

            #get file and save it to rooms path
            #file = request.files["file"]
            #here an intermediate step to convert file to .npy
            #file_path = os.path.join(room_path, 'file.npy')


            if request.form.get('centres') == 'ALL':
                idx = list(np.where(np.ones_like(data, dtype=bool)))[0]
            else:
                idx = list(np.where(data[request.form.get('centres')]))[0]

            random.shuffle(idx)

            if len(idx) < int(request.form.get('VIrequest')):
                flash('VI Requested larger than available sample. Maximum is %i' %(len(idx)))

                # try:
                #     shutil.rmtree(room_path)
                # except OSError as e:
                #     print("Error: %s : %s" % (room_path, e.strerror))

                return render_template(template, request=request, disabled=False, file_info=file_info, id=id, project=project)

            req['ncols'] = int(request.form.get('Ncols')) #number of columns in gallery grid #incorporate to html
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


            #input params for viewer

            #req['catpath'] = file_path
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


            if req['labels'] is not None:
                veto = {key:data[val] for key, val in zip(req['labels'].keys(), req['labels'].values())}
            else:
                veto = None

            if req['info_list'] is not None:
                info = {key:data[val] for key, val in zip(req['info_list'].keys(), req['info_list'].values())}
            else:
                info = None

            coord = [data[i] for i in req['coord_names']]

            print('==================================')
            _plots = {}
            for num, i in enumerate(batchs_idx):
                plots = html_postages(coord=coord, idx=i, veto=veto, info=info, layer_list=req['layers'], BoxSize=req['boxsize'])
                _plots['%i' %(num)] = plots
                #print('batch %s DONE...' %(str(num)))

            req['plots'] = _plots
            # Get elements of batchs_idx
            idxs = [item for sublist in batchs_idx for item in sublist]
            req['vi_query'] = {key:unclassified_label[0] for key in idxs}


            #save dict in room directory
            #np.save(os.path.join(room_path, 'requests'), req, allow_pickle=True)

            # for key in req.keys():
            #     print('%s: \t %s' %(key, req[key]))

            #Export user details of project and room and batchID to database

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
                               ncols=req['ncols'],
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
                               plots=req['plots'],
                               vi_query=req['vi_query']
                               )
            session.add(newentry)
            session.commit()
            session.close()


            batchID = 0 #assign first batchID

            pj = session.query(tracker).filter_by(project=req['project'], room=req['room'], email=req['email'], author=True).first()

            if pj:
                return redirect(url_for('create_entry', id=pj.id, name=req['name'], afilliation=req['afilliation'],
                                        email=req['email'], batchID=batchID))
                # entry_id = create_joiners_entry(id=pj.id, name=req['name'], afilliation=req['afilliation'], email=req['email'], batchID=batchID)
            else:
                raise ValueError('Project does not exist.')


            #return redirect(url_for('viewer', ProjectName=req.get('project'), RoomName=req.get('room'), user=req.get('email'), batchID=batchID))
            #return render_template('new_project.html', request=request, disabled=False, file_info=file_info)
    else:
        return render_template(template, disabled=True, file_info=file_info, id=id, project=project)

@app.route('/create_entry/<int:id>/<name>/<afilliation>/<email>/<int:batchID>')
def create_entry(id, name, afilliation, email, batchID):

    room_id, entry_id, batchID = create_joiners_entry(id=id, name=name, afilliation=afilliation, email=email, batchID=batchID)

    return redirect(url_for('viewer', room_id=room_id, entry_id=entry_id, batchID=batchID))


@app.route('/viewer/<int:room_id>/<int:entry_id>/<int:batchID>', methods=['GET', 'POST'])
def viewer(room_id, entry_id, batchID):

    pj_room = session.query(tracker).filter_by(id=room_id).first()
    if not pj_room:
        raise ValueError('No room with ID %i was found.' %(room_id))

    if entry_id is None:
        pj_entry = None
    else:
        pj_entry = session.query(tracker).filter_by(id=entry_id).one()

        if not pj_entry:
            raise ValueError('No entry with ID %i was found.' %(entry_id))

    if request.form.get('save') == 'continue':

        vi_query = {}

        for key in request.form:
            if key.startswith('class.'):
                id_ = key.partition('.')[-1]
                value = request.form[key]
                vi_query[int(id_)] = value
                print('%s \t %s' %(id_, value))

        try:
            pj_entry.vi_query = vi_query
            session.commit()
            flash('Entries saved successfully')
        except:
            raise ValueError('Error occurred when trying to save VI entries.')

    # pj_room = session.query(tracker).filter_by(id=pj.room_id).one()
    # if not pj_room:
    #     raise ValueError('No room with ID %i was found.' %(pj.room_id))

    # print('========= PD =========')
    # print(pj_room.plots.keys())
    # print(batchID)
    plot_dict = pj_room.plots[str(batchID)]
    #
    # print(plot_dict)

    html = render_template('room.html', pj_room=pj_room, pj_entry=pj_entry, batchID=batchID, plot_dict=plot_dict)
    return encode_utf8(html)

@app.route('/test_viewer', methods=['GET', 'POST'])
def test_viewer():

    ProjectName = 'BGS3'
    RoomName = 'faint'
    user = 'omar@ruiz'
    batchID = 0
    pjs = None

    reqPath = os.path.join(os.getcwd(), 'projects', ProjectName, RoomName, 'requests.npy')
    req = np.load(reqPath, allow_pickle=True).item()
    userfile_path = os.path.join(os.getcwd(), 'projects', ProjectName, RoomName, '%s_%s' %(user, str(batchID)))
    room_path = os.path.join(os.getcwd(), 'projects', ProjectName, RoomName)

    if request.form.get('save') == 'continue':

        vi_query = {}

        for key in request.form:
            if key.startswith('class.'):
                id_ = key.partition('.')[-1]
                value = request.form[key]
                vi_query[int(id_)] = value
                print('%s \t %s' %(id_, value))

        req['vi_query'] = vi_query
        np.save(os.path.join(room_path, 'requests'), req, allow_pickle=True)
        flash('Entries saved successfully')

    plots_dict = req['plots_batch_%s' %(str(batchID))]
    # script = plots_dict[0]
    # control_divs = plots_dict[1]['controls']
    # plot_divs = plots_dict[1].pop('controls')
    # print(plots_dict[1].keys())
    # script=plots_dict[0], plot_divs=plots_dict[1], control_divs=control_divs

    idx = req.get('%s_%s' %(RoomName, str(batchID)))


    #script = plots.values()[0]
    #div = plots.values()[1]

    html = render_template('room2.html', plots_dict=plots_dict, current_batch=batchID, user=user, req=req, pjs=pjs)
    return encode_utf8(html)

#galleries page
# @app.route('/<ProjectName>/<RoomName>/<user>/<int:batchID>', methods=['GET', 'POST'])
# def viewerOLD(ProjectName, RoomName, user, batchID):
# 
#     try:
# 
#         pjs = session.query(tracker).filter_by(project=ProjectName, room=RoomName).one()
#         session.close()
#         print('======== pjs ========')
#         print(pjs.status)
#     except:
#         pjs = None
#         print('No project %s found' %(ProjectName))
# 
#     if request.form.get('next') == 'continue':
# 
#         #print('===== HERE ======')
# 
#         batchID = find_batch_available(ProjectName, RoomName, user) #assign batchID based on availability
#         pathdir = os.path.join(os.getcwd(), 'projects', ProjectName, RoomName)
#         userfile_path = '%s/%s_%s' %(pathdir, user, str(batchID))
#         userfile_path_csv = '%s.csv' %(userfile_path)
#         #print(batchID, userfile_path_csv)
# 
#         if os.path.isfile(userfile_path_csv):
#             #print('========= enter ===========')
#             reqPath = os.path.join(os.getcwd(), 'projects', ProjectName, RoomName, 'requests.npy')
#             req = np.load(reqPath, allow_pickle=True).item()
# 
#             args = {}
#             args['batchID'] = batchID
#             args['reqPath'] = reqPath
#             args['userfile_path'] = userfile_path
#             flash('Hmmm, seems you have ran out of batchs in this room. You will be redirect to batch %i and continue where you left.' %(batchID+1))
# 
#             bokeh_script = server_document(url='http://localhost:5006/script', arguments=args)
#             return render_template('room.html', bokeh_script=bokeh_script, template="Flask", current_batch=batchID, user=user, req=req, pjs=pjs)
# 
#         else:
#             usr = session.query(tracker).filter_by(email=user).all()
#             session.close()
#             #add entry to database
#             newentry = tracker(project=ProjectName, room=RoomName, batch=batchID,
#                              name=usr[0].name, afilliation=usr[0].afilliation, email=usr[0].email, progress=int(0), status='open')
#             session.add(newentry)
#             session.commit()
#             session.close()
# 
#             return redirect(url_for('viewer', ProjectName=ProjectName, RoomName=RoomName, user=user, batchID=batchID))
# 
# 
#     reqPath = os.path.join(os.getcwd(), 'projects', ProjectName, RoomName, 'requests.npy')
#     req = np.load(reqPath, allow_pickle=True).item()
#     userfile_path = os.path.join(os.getcwd(), 'projects', ProjectName, RoomName, '%s_%s' %(user, str(batchID)))
#     userfile_path_csv = '%s.csv' %(userfile_path)
# 
#     idx = req.get('%s_%s' %(RoomName, str(batchID)))
#     Nbatchs = req['nbatchs']
# 
#     args = {}
#     args['batchID'] = batchID
#     args['reqPath'] = reqPath
# 
#     if (req.get('RGlabels') is not None) & (pjs.status == 'open'):
# 
#         print('===== inside ====')
# 
#         if not os.path.isfile(userfile_path_csv) :
# 
#             #create selections file
#             pddata = {'data':np.full(req.get('%s_Ndata' %(RoomName)), 'NA', dtype='S4')}
#             selections = pd.DataFrame(pddata, columns=["data"])
#             unclassified_label = ['UNCL']
# 
#             #get centres from batchID
#             selections.iloc[idx] = unclassified_label[0]
#             selections.to_csv('%s.csv' %(userfile_path), index=False)
# 
#             #If user not in database, create entry for that user
#             try:
#                 session.query(tracker).filter_by(project=ProjectName, room=RoomName, batch=batchID, email=user).one()
#             except:
#                 usr = session.query(tracker).filter_by(project=ProjectName, room=RoomName, email=user).all()
#                 print('Data entry does not exist. Creating new entry for this user')
#                 #add entry to database
#                 newentry = tracker(project=usr[0].project, room=usr[0].room, batch=batchID,
#                                  name=usr[0].name, afilliation=usr[0].afilliation, email=usr[0].email, progress=int(0), status='open')
#                 session.add(newentry)
#                 session.commit()
#                 session.close()
# 
#         args['userfile_path'] = userfile_path
#         bokeh_script = server_document(url='http://localhost:5006/script', arguments=args)
#         return render_template('room.html', bokeh_script=bokeh_script, template="Flask", current_batch=batchID, user=user, req=req, pjs=pjs)
# 
#     else:
# 
#         args['userfile_path'] = None
#         bokeh_script = server_document(url='http://localhost:5006/script', arguments=args)
#         return render_template('room.html', bokeh_script=bokeh_script, template="Flask", current_batch=batchID, user=user, req=req, pjs=pjs)

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
#                 usr = session.query(tracker).filter_by(email=user).all()
#                 session.close()
#                 #add entry to database
#                 newentry = tracker(project=project, room=room, batch=batchID,
#                                  name=usr[0].name, afilliation=usr[0].afilliation, email=usr[0].email, progress=int(0), status='open')
#                 session.add(newentry)
#                 session.commit()
#                 session.close()
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
                session.add(newentry)
                session.commit()
                session.close()

                return redirect(url_for('viewer', ProjectName=ProjectName, RoomName=RoomName, user=user, batchID=batchID))
    else:

        author = session.query(tracker).filter_by(room=RoomName, project=ProjectName).one()
        text = 'By %s from %s' %(author.name, author.afilliation)
        session.close()
        return render_template('join.html', button='Go to galleries', author=author, join=True)

@app.route('/resume', methods=['GET', 'POST'])
def resume():

    if request.method == 'POST':
        if request.form.get('make_gall') == 'continue':

            req = request.form
            email = req.get('email')

            usr = session.query(tracker).filter_by(email=email).all()
            session.close()
            pjs = session.query(tracker).filter_by(email=email).all()
            session.close()

            if (len(usr) > 0) or (len(pjs) > 0):
                return redirect(url_for('user_active_rooms', user=email))
            else:
                text = '%s does not have active rooms yet. Go to Projects to join an existing room.' %(email)
                flash(text)
                return render_template('join.html', button='Continue', join=False)

    return render_template('join.html', button='Continue', join=False)

@app.route('/current_rooms/<user>')
def user_active_rooms(user):

    rooms = session.query(tracker).filter_by(email=user).all()
    session.close()
    #username = user+'_'+rooms[0].afilliation

    print(user, rooms)

    if len(rooms) > 0:
        for room in rooms:
            progress = get_user_progress(ProjectName=room.project, RoomName=room.room,
                                       user=user, batchID=room.batch)
            room.progress = progress

        name = rooms[0].name
        print('======1=========')
        print(name)

    pjs = session.query(tracker).filter_by(email=user).all()
    session.close()
    if len(pjs) > 0:
        name = pjs[0].name
        print('======2=========')
        print(name)

    myprojects_open = session.query(tracker).filter_by(email=user, status='open', VI=True).all()
    myprojects_closed = session.query(tracker).filter_by(email=user, status='closed', VI=True).all()
    myprojects_nonVI = session.query(tracker).filter_by(email=user, VI=False).all()

    for myprojects in [myprojects_open, myprojects_closed]:
        for pj in myprojects:
            progress = get_room_progress(ProjectName=pj.project, RoomName=pj.room, VIreq=pj.VIreq)
            pj.progress = progress

    session.close()

    return render_template('user_active_rooms.html', rooms=rooms, myprojects_open=myprojects_open,
                           myprojects_closed=myprojects_closed, myprojects_nonVI=myprojects_nonVI,
                           name=name, user=user)

# This will let us Delete our book
@app.route('/delete/<ProjectName>/<RoomName>/<email>', methods=['GET', 'POST'])
def delete(ProjectName, RoomName, email):

    RoomToDelete = session.query(tracker).filter_by(project=ProjectName, room=RoomName).one()
    session.close()

    RoomToDelete_tracker = session.query(tracker).filter_by(project=ProjectName, room=RoomName).all()
    for room in RoomToDelete_tracker:
        session.delete(room)
        session.commit()
    session.close()

    pathdir = os.path.join(os.getcwd(), 'projects', ProjectName, RoomName)

    try:
        shutil.rmtree(pathdir)
    except OSError as e:
        print("Error: %s : %s" % (pathdir, e.strerror))

    #delete data from databases
    session.delete(RoomToDelete)
    session.commit()
    session.close()

    #print('========================= = = = = = = ')
    rooms_left = session.query(tracker).filter_by(project=ProjectName).all()
    session.close()
    if len(rooms_left) < 1:
        pathdir_project = os.path.abspath(os.getcwd())+'/projects/%s/' %(ProjectName)
        try:
            shutil.rmtree(pathdir_project)
        except OSError as e:
            print("Error: %s : %s" % (pathdir_project, e.strerror))

    if len(session.query(tracker).filter_by(email=email).all()) > 0:

        flash("Room %s Deleted Successfully" %(RoomName))
        return redirect(url_for('user_active_rooms', user=email))
    else:
        return redirect(url_for('home'))

    session.close()

@app.route('/<action>/<int:id>', methods=['GET', 'POST'])
def closed_open(id, action):

    room_to_close = session.query(tracker).filter_by(id=id).one()

    print('========= Room to close ==============')
    print(room_to_close.status)
    room_to_close.status = action
    session.commit()
    print(room_to_close.status)

    project = room_to_close.project
    room = room_to_close.room
    email = room_to_close.email
    session.close()

    rooms_tracker = session.query(tracker).filter_by(project=project, room=room).all()
    for room in rooms_tracker:
        room.status = action
        session.commit()
    session.close()

    flash('You have successfully %s Room %s' %(action, room))
    return redirect(url_for('user_active_rooms', user=email))

@app.route('/download/<int:id>')
def download_file(id):

    pj = session.query(tracker).filter_by(id=id).one()
    session.close()

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
    batchs_idx = []
    for i in range(req.get('Nbatchs')):
        batchs_idx += list(req.get('%s_%i' %(room, i)))

    for file in files:

        resdict[os.path.basename(file[:-4])] = np.array(pd.read_csv(file))

    rescat = np.hstack(list(resdict.values()))
    outfile = np.full(len(np.load(os.path.join(room_path, 'file.npy'))), np.nan, dtype=object)

    for i in batchs_idx:
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
    np.savetxt(VIindexes_file, batchs_idx, fmt='%i')

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
    #file_path = os.path.join(app.config["FILE_UPLOADS"], filename)

    return filename


def create_joiners_entry(id=None, name=None, afilliation=None, email=None, batchID=None):

    pj = session.query(tracker).filter_by(id=id).first()

    if pj:

        if pj.vi:

            print('======= batch =========')
            print(batchID)

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
            return id, None, batchID

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
        N += int(np.sum(pj.vi_query.values() != 'UNCL'))

    return np.round(100*N/pj_room.vi_req, 1)

def get_user_progress(ProjectName, RoomName, user, batchID):

    pathdir = os.path.join(os.getcwd(), 'projects', ProjectName, RoomName)
    file = "%s/%s_%i.csv" %(pathdir, user, batchID)

    reqPath = os.path.join(os.getcwd(), 'projects', ProjectName, RoomName, 'requests.npy')
    req = np.load(reqPath, allow_pickle=True).item()
    batchs_idx = req.get('%s_%s' %(RoomName, str(batchID)))
    tot = len(batchs_idx)

    progress = 0

    userfile = np.array(pd.read_csv(file)['data'], dtype=str)
    mask = (userfile != "b'NA'") & (userfile != 'UNCL')
    progress += int(np.sum(mask))

    return np.round(100*progress/tot, 1)


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
