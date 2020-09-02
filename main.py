from flask import Flask, redirect, url_for, render_template, request, session

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
        print(session)
        print(session['name0'])
        #print(req)
        #[i for i in list(req.keys()) if i.startswith('name')]
        #print(rooms)
        return redirect(url_for('rooms', ProjectName=req.get('inputProjName'), RoomName=req.get('name0')))
    else:
        return render_template('new_project.html')

# function to return key for any value
def get_key(my_dict, val):
    for key, value in my_dict.items():
         if val == value:
             return key

    return "key doesn't exist"

@app.route('/<ProjectName>/<RoomName>', methods=['GET', 'POST'])
def rooms(ProjectName, RoomName):

    url = '/%s/%s' %(ProjectName, RoomName)
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


if __name__ == '__main__':
    app.run(debug=True)
