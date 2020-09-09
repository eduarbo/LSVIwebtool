import os
import atexit
import random
import subprocess
import pandas as pd

import numpy as np
from bokeh.client import push_session
from flask import Flask, redirect, url_for, render_template, request, session
from bokeh.util.string import encode_utf8
from bokeh.embed.server import server_document, server_session
from bokeh.document.document import Document

import lscutoff as vi

app = Flask(__name__)

# Set the secret key to some random bytes. Keep this really secret!
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'

bokeh_process = subprocess.Popen(
    ['python', '-m', 'bokeh', 'serve', '--allow-websocket-origin=localhost:5006', 'script.py'], stdout=subprocess.PIPE)

@atexit.register
def kill_server():
    bokeh_process.kill()

@app.route('/')
@app.route('/home')
def home():
    return render_template('index.html')

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

            np.save('%s%s' %(projPath, 'requests'), req)

            #for each user
            pddata = {'data':np.full(len(data), 'NA', dtype='S4')}
            selections = pd.DataFrame(pddata, columns=["data"])
            unclassified_label = ['UNCL']
            idx = list(np.where(data[centre]))[0]
            selections.iloc[idx] = unclassified_label[0]
            userfile_path = '%s%s' %(pathdir, user)
            #np.save(userfile_path, selections)
            #np.savetxt(userfile_path+'.cvs', selections, fmt='%s')
            selections.to_csv(userfile_path+'.cvs', index=False)

            #Export user details of project and room and batchID to database
            batchID = 0 #assign batchID accorndingly to availability

            return redirect(url_for('viewer', ProjectName=req.get('inputProjName'), RoomName=req.get('inputRoomName'), user=user, batchID=batchID))
    else:
        return render_template('new_project.html')

@app.route('/<ProjectName>/<RoomName>/<user>/<batchID>')
def viewer(ProjectName, RoomName, user, batchID):

    print('....................PASSING THROUGHT HERE AGAIN!.................')

    reqPath = os.path.abspath(os.getcwd())+'/projects/%s/requests.npy' %(ProjectName)
    req = np.load(reqPath, allow_pickle=True).item()
    pathdir = os.path.abspath(os.getcwd())+'/projects/%s/%s/' %(ProjectName, RoomName)
    userfile_path = '%s%s' %(pathdir, user)
    #get centres from batchID
    idx = req.get('%s_%s' %(RoomName, str(batchID)))
    print(idx)

    #args = {key:req.get(key)  for key in ['catpath', 'labels', 'coord_names', 'info_list', 'layer_list', 'centre', 'RGlabels']}
    args = {'userfile_path':userfile_path, 'idx':idx}

    bokeh_script = server_document(url='http://localhost:5006/script', arguments=args)
    return render_template('room.html',bokeh_script=bokeh_script)

# function to return key for any value
def get_key(my_dict, val):
    for key, value in my_dict.items():
         if val == value:
             return key

    return "key doesn't exist"



if __name__ == '__main__':
    app.run(debug=True)
