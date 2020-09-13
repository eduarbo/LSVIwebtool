import glob
import os
import atexit
import random
import subprocess
import pandas as pd

import numpy as np
from bokeh.client import push_session
from flask import Flask, redirect, url_for, render_template, request
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

    pjs = session_projects.query(VIprojects).all()

    print('=================================')
    for pj in pjs:
        print(pj.VIreq, pj.room, pj.status)
        progress = get_room_status(ProjectName=pj.project, RoomName=pj.room, VIreq=pj.VIreq)
        pj.status = progress
        #session_projects.commit()
    session_projects.close()

    return render_template('index.html', pjs=pjs)

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
            for num, i in enumerate(idxs):
                req['%s_%s' %(roomname, str(num))] = np.array(i)

            req['%s_Nbatchs' %(roomname)] = Nbatchs
            req['%s_Ndata' %(roomname)] = len(data)

            np.save('%s%s' %(projPath, 'requests'), req)

            #Export user details of project and room and batchID to database
            batchID = 0 #assign first batchID

            #add entry to tracker's database
            newentry = tracker(project=req.get('inputProjName'), room=req.get('inputRoomName'), batch=batchID,
                             name=name, afilliation=afill, email=email, status=int(0))
            session_tracker.add(newentry)
            session_tracker.commit()

            #add entry to projects database for each room
            newentry = VIprojects(project=req.get('inputProjName'), room=req.get('inputRoomName'),
                             name=name, afilliation=afill, email=email, VIreq=Nreq, status=int(0))
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

    # print('================== ROOMS ========================')
    # rooms = session_tracker.query(tracker).all()
    # for room in rooms:
    #     print(room.name)
    #
    # print('================== ROOMS ========================')
    # pj = session_projects.query(VIprojects).all()
    # for p in pj:
    #     print(p.VIreq, p.name)

    if not os.path.isfile(userfile_path_csv):

        #create selections file
        pddata = {'data':np.full(req.get('%s_Ndata' %(RoomName)), 'NA', dtype='S4')}
        selections = pd.DataFrame(pddata, columns=["data"])
        unclassified_label = ['UNCL']

        #get centres from batchID
        selections.iloc[idx] = unclassified_label[0]
        selections.to_csv('%s.cvs' %(userfile_path), index=False)

    #args = {key:req.get(key)  for key in ['catpath', 'labels', 'coord_names', 'info_list', 'layer_list', 'centre', 'RGlabels']}
    args = {'userfile_path':userfile_path, 'idx':idx}

    bokeh_script = server_document(url='http://localhost:5006/script', arguments=args)
    return render_template('room.html',bokeh_script=bokeh_script)

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
                                 name=name, afilliation=afill, email=email, status=int(0))
                session_tracker.add(newentry)
                session_tracker.commit()

                return redirect(url_for('viewer', ProjectName=ProjectName, RoomName=RoomName, user=user, batchID=batchID))
    #else:
    return render_template('join.html')

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

def get_user_status(ProjectName, RoomName):
    pass

def get_room_status(ProjectName, RoomName, VIreq):

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



if __name__ == '__main__':
    app.run(debug=True)
