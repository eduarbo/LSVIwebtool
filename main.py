import os

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
        req = request.form
        for key, val in zip(req.keys(), req.values()):
            session[key] = val
        #print(session)
        #print(session['name0'])

        if request.form.get('make_gall') == 'continue':

            #url = '/%s/%s' %(ProjectName, RoomName)

            #request values
            #create room directory to store data and users VI files
            pathdir = os.path.abspath(os.getcwd())+'/projects/%s/%s/' %(req.get('inputProjName'), req.get('inputRoomName'))
            #print(pathdir)
            #ispathdir = os.path.isdir(pathdir)
            #if not ispathdir:
            os.makedirs(pathdir, exist_ok=True)

            #prepare data
            data = np.load(pathdir+'VITestFile.npy')

            #input data
            veto = {'BGS':data['bgs'],'Not BGS':data['not_bgs']}
            info_list = ['RA', 'DEC', 'RMAG', 'GMAG', 'ZMAG', 'TYPE']
            info = {key:data[key] for key in info_list}
            dr, survey = 'dr8', 'south'
            layer_list = ['%s-%s' %(dr, survey), '%s-%s-model' %(dr, survey), '%s-%s-resid' %(dr, survey)]
            coord = [data['RA'], data['DEC']]
            idx = list(np.where(data['centre']))[0]
            RGlabels = ["STAR", "GAL", "CONT", "OTHR"]
            unclassified_label = 'UNCL'
            RGlabels.append(unclassified_label)
            title = None
            main_text = None
            buttons_text = None
            grid = [10,4]
            savefile = None
            print('===================================')
            print(len(idx))

            #create user array
            selections = np.full(len(data), 'NA', dtype='S4')
            selections[idx] = unclassified_label
            email = session['inputSubmitterEmail']
            afill = session['inputSubmitterAfill']
            user = '%s_%s' %(email, afill)
            cvsfile = '%s%s' %(pathdir, user)
            #np.savetxt(cvsfile, selections, fmt='%s')
            np.save(cvsfile, selections)

            #create galleries
            js_resources, css_resources, script1, div1 = vi.html_postages(coord=coord, idx=idx, veto=veto, info=info, grid=grid, layer_list=layer_list, title=title,
                      main_text=main_text, buttons_text=buttons_text, savefile=savefile, notebook=False, RGlabels=RGlabels, output=cvsfile)

            proj_dict = {'cvsfile':cvsfile, 'js_resources':js_resources, 'css_resources':css_resources, 'script1':script1, 'div1':div1}
            np.save(pathdir+'core', proj_dict, allow_pickle=True)
            #for key, val in zip(proj_dict.keys(), proj_dict.values()):
                #print(key)
            session['core'] = pathdir+'core'+'.npy'
            print('============1============')
            print(session.keys())

            return redirect(url_for('galleries', ProjectName=req.get('inputProjName'), RoomName=req.get('inputRoomName'), user=user))
    else:
        return render_template('new_project.html')


@app.route('/<ProjectName>/<RoomName>/<user>', methods=['GET', 'POST'])
def galleries(ProjectName, RoomName, user):

    #if request.method == 'GET':

    # document = Document()
    # document.add_root(grid)
    #document.add_root(controls)
    # session = push_session(document, session_id=None)
    # body = server_session(None, session_id=session.id)
    #return render_template('bokeh_test.html', body=body)

    core = os.path.abspath(os.getcwd())+'/projects/%s/%s/core.npy' %(ProjectName, RoomName, )
    proj_dict = np.load(core, allow_pickle=True).item()

    #return render_template('gallery_base.html', ProjectName=ProjectName, RoomName=RoomName, url=url)
    html = render_template(
        'bokeh_test.html',
        plot_script1=proj_dict['script1'],
        plot_div1=proj_dict['div1'],
        js_resources=proj_dict['js_resources'],
        css_resources=proj_dict['css_resources'],
        title=RoomName,
        cvsfile=proj_dict['cvsfile']
    )
    return encode_utf8(html)

# function to return key for any value
def get_key(my_dict, val):
    for key, value in my_dict.items():
         if val == value:
             return key

    return "key doesn't exist"

'''
 rooms = [i for i in list(session.keys()) if i.startswith('name')]
    rooms_names = [session[i] for i in rooms]
    rooms_urls = ['/%s/%s' %(ProjectName, i) for i in rooms_names]
    print(rooms, len(rooms), get_key(session, RoomName))
    roomN = int(get_key(session, RoomName)[-1])

    if request.method == 'POST':
        if request.form.get('continue') == 'Previous':
            if roomN == 0:
                return redirect(url_for('new_projects'))
            else:
                return redirect(url_for('rooms', ProjectName=ProjectName, RoomName=session['name'+str(roomN-1)]))
        elif request.form.get('continue') == 'Next Room':
            if roomN == len(rooms) - 1:
                #redirect to Galleries
                return redirect(url_for('rooms', ProjectName=ProjectName, RoomName=session['name'+str(roomN+1)]))
            else:
                return redirect(url_for('rooms', ProjectName=ProjectName, RoomName=session['name'+str(roomN+1)]))
        else:
            ValueError('Error!')
    else:
        return render_template('room_form.html', ProjectName=ProjectName, RoomName=RoomName, url=url, rooms_names=rooms_names, rooms_urls=rooms_urls)
    
'''


if __name__ == '__main__':
    app.run(debug=True)
