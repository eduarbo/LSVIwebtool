import glob
import os
import atexit
import random
import shutil
import subprocess
import pandas as pd

import numpy as np
from bokeh.client import push_session
from flask import Flask, redirect, url_for, render_template, request, flash
from bokeh.util.string import encode_utf8
from bokeh.embed.server import server_document, server_session
from bokeh.document.document import Document

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

bokeh_process = subprocess.Popen(
    ['python', '-m', 'bokeh', 'serve', '--allow-websocket-origin=localhost:5006', 'script.py'], stdout=subprocess.PIPE)

@atexit.register
def kill_server():
    bokeh_process.kill()

@app.route('/')
@app.route('/home')
def home():

    pjs_open = session_projects.query(VIprojects).filter_by(status='open').all()
    pjs_closed = session_projects.query(VIprojects).filter_by(status='closed').all()

    print('=================================')
    for pjs in [pjs_open, pjs_closed]:
        for pj in pjs:
            #print(pj.VIreq, pj.room, pj.progress)
            progress = get_room_progress(ProjectName=pj.project, RoomName=pj.room, VIreq=pj.VIreq)
            pj.progress = progress
            #session_projects.commit()
    session_projects.close()

    return render_template('index.html', myprojects_open=pjs_open, myprojects_closed=pjs_closed)

@app.route('/start')
def start():
    return render_template('start.html')

@app.route('/projects')
def projects():
    return render_template('projects.html')

@app.route('/new_project', methods=['GET', 'POST'])
def new_projects():
    if request.method == 'POST':
        req = {}
        req_ = request.form
        for key, val in zip(req_.keys(), req_.values()):
            req[key] = val

        if request.form.get('make_gall') == 'continue':

            #create project directory root
            pathdir = os.path.abspath(os.getcwd())+'/projects/%s/%s/' %(req.get('inputProjName'), req.get('inputRoomName'))
            projPath = os.path.abspath(os.getcwd())+'/projects/%s/' %(req.get('inputProjName'))
            os.makedirs(pathdir, exist_ok=True)

            email = req.get('inputSubmitterEmail')
            afill = req.get('inputSubmitterAfill')
            name = req.get('inputSubmitterName')
            user = '%s_%s' %(email, afill)

            #create user array
            if req.get('catpath') is not None: #pass this as a string
                catpath = req.get('catpath')
            else:
                catpath = os.path.abspath(os.getcwd())+'/projects/_files/VITestFile.npy'

            if req.get('centre') is not None:#pass this as a string
                centre = req.get('centre')
            else:
                centre = 'centre'

            #for each ROOM
            rows, cols = 5, 2 #req.get('rows'), req.get('cols')
            Nsamples = rows*cols
            Nreq = 40 #req.get('Nreq')
            Nbatchs = int(Nreq/Nsamples)
            grid = [rows,cols]

            data = np.load(catpath)
            idx = list(np.where(data[centre]))[0]
            random.shuffle(idx)
            idxs = idx[:Nreq].reshape(Nbatchs,Nsamples)
            roomname = req.get('inputRoomName')
            #print('================== req rooms ====================')
            for num, i in enumerate(idxs):
                req['%s_%s' %(roomname, str(num))] = np.array(i)
                #print(req['%s_%s' %(roomname, str(num))])

            req['%s_Nbatchs' %(roomname)] = Nbatchs
            #print(req['%s_Nbatchs' %(roomname)])
            req['%s_Ndata' %(roomname)] = len(data)


            np.save('%s%s' %(projPath, 'requests'), req)

            #Export user details of project and room and batchID to database
            batchID = 0 #assign first batchID

            #add entry to tracker's database
            newentry = tracker(project=req.get('inputProjName'), room=req.get('inputRoomName'), batch=batchID,
                             name=name, afilliation=afill, email=email, progress=int(0), status='open')
            session_tracker.add(newentry)
            session_tracker.commit()

            #add entry to projects database for each room
            newentry = VIprojects(project=req.get('inputProjName'), room=req.get('inputRoomName'),
                             name=name, afilliation=afill, email=email, VIreq=Nreq, progress=int(0), status='open')
            session_projects.add(newentry)
            session_projects.commit()

            return redirect(url_for('viewer', ProjectName=req.get('inputProjName'), RoomName=req.get('inputRoomName'), user=user, batchID=batchID))
    else:
        return render_template('new_project.html')

#galleries page
@app.route('/<ProjectName>/<RoomName>/<user>/<int:batchID>')
def viewer(ProjectName, RoomName, user, batchID):

    reqPath = os.path.abspath(os.getcwd())+'/projects/%s/requests.npy' %(ProjectName)
    req = np.load(reqPath, allow_pickle=True).item()
    pathdir = os.path.abspath(os.getcwd())+'/projects/%s/%s/' %(ProjectName, RoomName)
    userfile_path = '%s%s_%s' %(pathdir, user, str(batchID))
    userfile_path_csv = '%s.cvs' %(userfile_path)
    idx = req.get('%s_%s' %(RoomName, str(batchID)))
    Nbatchs = req['%s_Nbatchs' %(RoomName)]

    # print('================== ROOMS ========================')
    # rooms = session_tracker.query(tracker).all()
    # for room in rooms:
    #     print(room.name)
    #
    #print('================== ROOMS ========================')

    session_tracker.close()
    # pj = session_projects.query(VIprojects).all()
    # for p in pj:
    #  print(p.status, p.progress)
    # session_projects.close()

    if not os.path.isfile(userfile_path_csv):

        #create selections file
        pddata = {'data':np.full(req.get('%s_Ndata' %(RoomName)), 'NA', dtype='S4')}
        selections = pd.DataFrame(pddata, columns=["data"])
        unclassified_label = ['UNCL']

        #get centres from batchID
        selections.iloc[idx] = unclassified_label[0]
        selections.to_csv('%s.cvs' %(userfile_path), index=False)

        try:
            session_tracker.query(tracker).filter_by(project=ProjectName, room=RoomName, batch=batchID, email=user.split('_')[0]).one()
        except:
            usr = session_tracker.query(tracker).filter_by(project=ProjectName, room=RoomName, email=user.split('_')[0]).all()
            print('Data entry does not exist. Creating new entry for this user')
            #add entry to database
            newentry = tracker(project=usr[0].project, room=usr[0].room, batch=batchID,
                             name=usr[0].name, afilliation=usr[0].afilliation, email=usr[0].email, progress=int(0), status='open')
            session_tracker.add(newentry)
            session_tracker.commit()
            session_tracker.close()

    #args = {key:req.get(key)  for key in ['catpath', 'labels', 'coord_names', 'info_list', 'layer_list', 'centre', 'RGlabels']}
    args = {'userfile_path':userfile_path, 'idx':idx}

    bokeh_script = server_document(url='http://localhost:5006/script', arguments=args)
    return render_template('room.html',bokeh_script=bokeh_script, Nbatchs=Nbatchs, current_batch=batchID, project=ProjectName, room=RoomName, user=user)

#/
#
@app.route('/join/<ProjectName>/<RoomName>/', methods=['GET', 'POST'])
def join(ProjectName, RoomName):
    '''
   If joining a project room by clicking to a specific entry on projects/rooms status table,
   you will have to identify yourself first
    '''

    if request.method == 'POST':
        print('IS HERE!!!!!!!!!!!!')
        if request.form.get('make_gall') == 'continue':

            req = request.form
            name = req.get('name')
            email = req.get('email')
            afill = req.get('afilliation')
            user = '%s_%s' %(email, afill)

            #Export user details of project and room and batchID to database
            batchID = find_batch_available(ProjectName, RoomName, user) #assign batchID based on availability
            print('batchID', batchID)
            pathdir = os.path.abspath(os.getcwd())+'/projects/%s/%s/' %(ProjectName, RoomName)
            userfile_path = '%s%s_%s' %(pathdir, user, str(batchID))
            userfile_path_csv = '%s.cvs' %(userfile_path)

            if os.path.isfile(userfile_path_csv):
                print('Hmmm, seems you have ran out of batchs in this room. You will be redirect to batch %i and continue where you left.' %(batchID))
                return redirect(url_for('viewer', ProjectName=ProjectName, RoomName=RoomName, user=user, batchID=batchID))
            else:
                #add entry to database
                newentry = tracker(project=ProjectName, room=RoomName, batch=batchID,
                                 name=name, afilliation=afill, email=email, progress=int(0), status='open')
                session_tracker.add(newentry)
                session_tracker.commit()

                return redirect(url_for('viewer', ProjectName=ProjectName, RoomName=RoomName, user=user, batchID=batchID))
    #else:
    author = session_projects.query(VIprojects).filter_by(room=RoomName, project=ProjectName).one()
    text = 'By %s from %s' %(author.name, author.afilliation)
    session_projects.close()
    return render_template('join.html', title='Join %s' %(RoomName), button='Go to galleries', text=text)

@app.route('/resume', methods=['GET', 'POST'])
def resume():

    if request.method == 'POST':
        if request.form.get('make_gall') == 'continue':

            req = request.form
            name = req.get('name')
            email = req.get('email')
            afill = req.get('afilliation')

            user = session_tracker.query(tracker).filter_by(email=email).all()
            session_tracker.close()
            if len(user) > 0:
                return redirect(url_for('user_active_rooms', user=email))
            else:

                text = '%s does not have active rooms yet. Go to Projects to join an existing room.' %(email)
                flash(text)
                return render_template('join.html', title='Resume your Rooms', button='Continue')

    return render_template('join.html', title='Resume your Rooms', button='Continue')

@app.route('/current_rooms/<user>')
def user_active_rooms(user):

    rooms = session_tracker.query(tracker).filter_by(email=user).all()
    username = user+'_'+rooms[0].afilliation

    for room in rooms:
        progress = get_user_progress(ProjectName=room.project, RoomName=room.room,
                                   user='%s_%s' %(room.email, room.afilliation), batchID=room.batch)
        room.progress = progress
    session_tracker.close()


    myprojects_open = session_projects.query(VIprojects).filter_by(email=user, status='open').all()
    myprojects_closed = session_projects.query(VIprojects).filter_by(email=user, status='closed').all()

    for myprojects in [myprojects_open, myprojects_closed]:
        for pj in myprojects:
            progress = get_room_progress(ProjectName=pj.project, RoomName=pj.room, VIreq=pj.VIreq)
            pj.progress = progress

    session_projects.close()

    return render_template('user_active_rooms.html', rooms=rooms, myprojects_open=myprojects_open, myprojects_closed=myprojects_closed, name=rooms[0].name, user=username)

# This will let us Delete our book
@app.route('/delete/<ProjectName>/<RoomName>/<email>', methods=['GET', 'POST'])
def delete(ProjectName, RoomName, email):

    RoomToDelete = session_projects.query(VIprojects).filter_by(project=ProjectName, room=RoomName).one()
    RoomToDelete_tracker = session_tracker.query(tracker).filter_by(project=ProjectName, room=RoomName).all()

    pathdir = os.path.abspath(os.getcwd())+'/projects/%s/%s/' %(ProjectName, RoomName)

    try:
        shutil.rmtree(pathdir)
    except OSError as e:
        print("Error: %s : %s" % (pathdir, e.strerror))

    #delete data from databases
    session_projects.delete(RoomToDelete)
    session_projects.commit()
    session_projects.close()

    print('========================= = = = = = = ')
    rooms_left = session_projects.query(VIprojects).filter_by(project=ProjectName).all()
    if len(rooms_left) < 1:
        pathdir_project = os.path.abspath(os.getcwd())+'/projects/%s/' %(ProjectName)
        try:
            shutil.rmtree(pathdir_project)
        except OSError as e:
            print("Error: %s : %s" % (pathdir_project, e.strerror))


    for room in RoomToDelete_tracker:
        session_tracker.delete(room)
        session_tracker.commit()
    session_tracker.close()

    flash("Room %s Deleted Successfully" %(RoomName))
    return redirect(url_for('user_active_rooms', user=email))

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


# def delete(ProjectName, RoomName, email):
#     RoomToDelete = session_projects.query(VIprojects).filter_by(project=ProjectName, room=RoomName).one()
#     RoomToDelete_tracker = session_tracker.query(tracker).filter_by(project=ProjectName, room=RoomName).all()
#     if request.method == 'POST':
#         if request.form.get('delete') == 'yes':
#
#             #remove directory
#             pathdir = os.path.abspath(os.getcwd())+'/projects/%s/%s/' %(ProjectName, RoomName)
#
#             try:
#                 shutil.rmtree(pathdir)
#             except OSError as e:
#                 print("Error: %s : %s" % (pathdir, e.strerror))
#
#             #delete data from databases
#             session_projects.delete(RoomToDelete)
#             session_projects.commit()
#             session_projects.close()
#
#             for room in RoomToDelete_tracker:
#                 session_tracker.delete(room)
#                 session_tracker.commit()
#             session_tracker.close()
#
#             return redirect(url_for('user_active_rooms', user=email))
#         if request.form.get('delete') == 'no':
#             return redirect(url_for('user_active_rooms', user=email))
#     else:
#         return render_template('delete.html', room=RoomToDelete)

def find_batch_available(ProjectName, RoomName, user):

    reqPath = os.path.abspath(os.getcwd())+'/projects/%s/requests.npy' %(ProjectName)
    req = np.load(reqPath, allow_pickle=True).item()
    Nbatchs = req.get('%s_Nbatchs' %(RoomName))

    pathdir = os.path.abspath(os.getcwd())+'/projects/%s/%s/' %(ProjectName, RoomName)
    files = glob.glob("%s/*.cvs" %(pathdir))

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
        files = glob.glob("%s/%s*.cvs" %(pathdir, user))
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

    pathdir = os.path.abspath(os.getcwd())+'/projects/%s/%s/' %(ProjectName, RoomName)
    file = "%s/%s_%i.cvs" %(pathdir, user, batchID)

    reqPath = os.path.abspath(os.getcwd())+'/projects/%s/requests.npy' %(ProjectName)
    req = np.load(reqPath, allow_pickle=True).item()
    idxs = req.get('%s_%s' %(RoomName, str(batchID)))
    tot = len(idxs)

    #print('==========================')
    #print(ProjectName, RoomName, user, batchID, idxs, type(idxs))

    progress = 0

    userfile = np.array(pd.read_csv(file)['data'], dtype=str)
    mask = (userfile != "b'NA'") & (userfile != 'UNCL')
    progress += int(np.sum(mask))

    return np.round(100*progress/tot, 1)

def get_room_progress(ProjectName, RoomName, VIreq):

    pathdir = os.path.abspath(os.getcwd())+'/projects/%s/%s/' %(ProjectName, RoomName)
    files = glob.glob("%s/*.cvs" %(pathdir))

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

'''
          <h2>My projects</h2>
          <ol>
            {% for pj in myprojects %}
              <li> {{pj.id}}  {{pj.project}} {{pj.room}} {{pj.afilliation}} {{pj.status}}
                <a href="{{url_for('delete', ProjectName=pj.project, RoomName=pj.room, email=pj.email)}}"><button class="btn btn-danger">Delete</button></a>
                <a><button class="btn btn-success">Download</button></a></li>
              <br> <br>
            {% endfor %}
          </ol>
'''


if __name__ == '__main__':
    app.run(debug=True)
