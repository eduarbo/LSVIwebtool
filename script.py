#
from functools import partial

import numpy as np
import os
import pandas as pd

import bokeh.plotting as bk
from bokeh.models import ColumnDataSource, ImageURL, CustomJS, Span, OpenURL, TapTool, Div
from bokeh.models.widgets import CheckboxGroup, RadioGroup, Widget, Button, Slider
from bokeh.layouts import gridplot, row, column, WidgetBox
from bokeh.io import curdoc
from bokeh.plotting import figure

def coordtopix(center, coord, size, scale):

    RA_pix = []
    DEC_pix = []
    for i in range(len(coord[0])):
        d_ra = (center[0]-coord[0][i])*3600
        d_dec = (center[1]-coord[1][i])*3600
        if d_ra > 180*3600:
            d_ra = d_ra - 360.*3600
        elif d_ra < -180*3600:
            d_ra = d_ra + 360.*3600
        else:
            d_ra = d_ra
        d_ra = d_ra * np.cos(coord[1][i]/180*np.pi)

        ra_pix = size/2. + d_ra/scale
        dec_pix = size/2. - d_dec/scale
        RA_pix.append(ra_pix)
        DEC_pix.append(dec_pix)

    return RA_pix, DEC_pix


def html_postages(coord=None, idx=None, notebook=True, savefile=None, htmltitle='page', veto=None, info=None, m=4,
                  radius=4/3600, comparison=None, layer_list=None, tab=False, tab_title=None,
                  RGlabels=None, output=None, userfile_path=None, Ncols=4, BoxSize=40):

    '''

    Parameters
    ----------
    coord : list
        List with RA and DEC columns.
    idx : numpy array
        Array of indexes from coord list where postages will be centred.
    notebook : bool, optional
        True if running from jupyter notebook.
    savefile : string, optional
        path where html file will be saved
    htmltitle : string, optional
        title of webpage.
    veto : dict, bool, numpy array, optional
        dictionary with numpy array booleans with lenght of coord parameter. If not None, targets within postages are classified accordingly.
    info : dict, bool, numpy array, optional
        dictionary with numpy array parameters with lenght of coord parameter. If not None, a tooltip for each target containing dict parameters is created.
    grid : 2D-list, optional
        list with gallery size of the form [rows, columns]. Default is 2x2 grid.
    m : int, optional
        Scale factor for postage boxsize. Boxsize is defined as 2*m*radius*3600. Default is set to 4.
    radius : int, float, optional
        radius in degrees of postage boxsize. Default is set to 4/3600.
    comparison : deprecated
    layer_list : list, numpy array, optional
        list of Legacy Survey layers to include in postages. Default are ['dr9f-south', 'dr9f-south-model', 'dr9f-south-resid', 'dr9g-south', 'dr9g-south-model', 'dr9g-south-resid', 'dr9f-north', 'dr9f-north-model', 'dr9f-north-resid', 'dr9g-north', 'dr9g-north-model', 'dr9g-north-resid']
    title : string, optional
        title to show for gallery.
    tab : bool, optional
        If true, output gallery is a html tab. Default is False.
    tab_title : string, optional
        Title of tab.
    main_text : string, optional
        Some body text of gallery. Default is None.
    button_text : string, optional
        Some text above checkboxes if any. Default is None.

    '''

    if notebook: bk.output_notebook()
    if savefile is not None:
        html_page = savefile + '.html'
        bk.output_file(html_page, title=htmltitle)
        print(html_page)

    plots = []
    sources = []
    layers = []
    plots_i = []

    if userfile_path is not None:
        userfile = pd.read_csv(userfile_path + '.cvs')
        current_RGval = userfile['data']

    if RGlabels is not None:
        RGlabels_id = {key:i for i, key in enumerate(RGlabels)}

    def my_radio_handler(event, idx, num):
        print(event, RGlabels[event], idx, num, RGlabels[-1])

        p = plots_i[num]
        if RGlabels[event] == RGlabels[-1]: p.outline_line_color = "red"
        else: p.outline_line_color = "green"

        if userfile_path is not None:
            userfile = pd.read_csv(userfile_path + '.cvs')
            print(userfile_path)
            userfile.iloc[idx] = str(RGlabels[event])
            userfile.to_csv(userfile_path+'.cvs', index=False)

    if comparison is not None: a, b = comparison[0], comparison[1]

    RA, DEC = coord[0], coord[1]
    scale_unit='pixscale'
    scale=0.262
    boxsize = BoxSize #2*m*radius*3600
    radius = BoxSize/(2 * 3600)
    size = int(round(boxsize/scale))
    figsize = int(128)
    print('BoxSize', boxsize)
    print('Size', size)

    idx_list = idx #random.sample(list(idx), rows*cols)

    if info is None:
        info = {'RA':RA, 'DEC':DEC}

    if veto is None:
        veto = {'all':np.ones_like(RA, dtype=bool)}

    if layer_list is None:

        layer_list = ['dr9f-south', 'dr9f-south-model', 'dr9f-south-resid', 'dr9g-south', 'dr9g-south-model', 'dr9g-south-resid',
                 'dr9f-north', 'dr9f-north-model', 'dr9f-north-resid', 'dr9g-north', 'dr9g-north-model', 'dr9g-north-resid']

    if True:

        for num, idx in enumerate(idx_list):

            RAidx = RA[idx]
            DECidx = DEC[idx]

            ramin, ramax = RAidx-radius, RAidx+radius
            decmin, decmax = DECidx-radius, DECidx+radius
            dra = (ramax - ramin)/40
            ddec = (decmax - decmin)/40
            mask = (RA > ramin + dra) & (RA < ramax - dra) & (DEC > decmin + ddec) & (DEC < decmax - ddec)

            TOOLTIPS = []

            for key in info.keys():
                TOOLTIPS.append((key, '@'+key))

            p = figure(plot_width=2*figsize, plot_height=2*figsize, tooltips=TOOLTIPS, tools="tap, save, zoom_in, zoom_out, crosshair")
            p.axis.visible = False
            #p.min_border = 0

            layers2 = []
            for layer in layer_list:

                source='http://legacysurvey.org/viewer-dev/jpeg-cutout/?ra=%.12f&dec=%.12f&%s=%g&layer=%s&size=%g' % (RAidx, DECidx, scale_unit, scale, layer, size)
                url='http://legacysurvey.org/viewer-dev?ra=%.12f&dec=%.12f&layer=%s&zoom=15' %(RAidx, DECidx, layer)
                imfig_source = ColumnDataSource(data=dict(url=[source], txt=[source]))
                image1 = ImageURL(url="url", x=0, y=1, w=size, h=size, anchor='bottom_left')
                img_source = p.add_glyph(imfig_source, image1)

                layers2.append(img_source)

            taptool = p.select(type=TapTool)
            taptool.callback = OpenURL(url=url)

            colors = ['green', 'red', 'blue', 'cyan', 'yellow']
            circle_i = []
            for color, key, val in zip(colors, veto.keys(), veto.values()):
                #print('=====================')
                #print(key, len(val))

                ravpix, decvpix = coordtopix(center=[RAidx, DECidx], coord=[RA[(mask) & (val)], DEC[(mask) & (val)]], size=size, scale=scale)

                data = {}
                data['x'] = ravpix
                data['y'] = decvpix
                #print('x', len(ravpix))
                for info_key, info_val in zip(info.keys(), info.values()):
                    data[info_key] = np.array(info_val)[(mask) & (val)]
                    #print(len(ravpix), len(decvpix), len(np.array(info_val)[(mask) & (val)]))


                sourceCirc = ColumnDataSource(data=data)

                circle = p.circle('x', 'y', source=sourceCirc, size=15, fill_color=None, line_color=color, line_width=3)
                circle_i.append(circle)

            lineh = Span(location=size/2, dimension='height', line_color='white', line_dash='solid', line_width=1)
            linew = Span(location=size/2, dimension='width', line_color='white', line_dash='solid', line_width=1)

            p.add_layout(lineh)
            p.add_layout(linew)
            p.background_fill_color = "black"
            p.outline_line_width = 15
            p.outline_line_alpha = 0.7
            #print('==================')
            #print(current_RGval.iloc[idx], RGlabels[-1])

            p.xgrid.grid_line_color = None
            p.ygrid.grid_line_color = None

            if RGlabels is not None:

                if current_RGval.iloc[idx] == RGlabels[-1]:
                    p.outline_line_color = "red"
                else:
                    p.outline_line_color = "green"

                #print(idx, current_RGval.iloc[idx])#, RGlabels_id[current_RGval.iloc[idx]])
                rbt = RadioGroup(labels=RGlabels, active=RGlabels_id[current_RGval.iloc[idx]], sizing_mode='scale_height')
                #default_size=20 width_policy='min', sizing_mode="scale_both"
                rbt.on_click(partial(my_radio_handler, idx=idx, num=num))
                plots.append(row(children=[p, rbt]))
                plots_i.append(p)
            else:
                plots.append(p)

            sources.append(circle_i)
            layers.append(layers2)

    def update_width(attr, old, new):
        for p in plots_i:
            #print(old, new)
            p.width=figsize*new
            p.height=figsize*new

    #button = Button()
    size_slider = Slider(start=1, end=5, value=2, step=1, title="Figure Size")
    size_slider.on_change("value", update_width)

    checkbox = CheckboxGroup(labels=list(veto.keys()), active=list(np.arange(len(veto))))
    iterable = [elem for part in [[('_'.join(['line',str(figid),str(lineid)]),line) for lineid,line in enumerate(elem)] for figid,elem in enumerate(sources)] for elem in part]
    checkbox_code = ''.join([elem[0]+'.visible=checkbox.active.includes('+elem[0].split('_')[-1]+');' for elem in iterable])
    callback = CustomJS(args={key:value for key,value in iterable+[('checkbox',checkbox)]}, code=checkbox_code)
    checkbox.js_on_click(callback)

    radio = RadioGroup(labels=layer_list, active=len(layer_list)-1)
    iterable2 = [elem for part in [[('_'.join(['line',str(figid),str(lineid)]),line) for lineid,line in enumerate(elem)] for figid,elem in enumerate(layers)] for elem in part]
    #
    N = len(layer_list)
    text = []
    for elem in iterable2[::N]:
        for n in range(N):
            text.append('%s%s.visible=false;' %(elem[0][:-1], str(n)))
        for n in range(N):
            if n == 0: text.append('if (cb_obj.active == 0) {%s%s.visible = true;}' %(elem[0][:-1], str(0)))
            if n != 0: text.append('else if (cb_obj.active == %s) {%s%s.visible = true;}' %(str(n), elem[0][:-1], str(n)))

        radiogroup_code = ''.join(text)

    callback2 = CustomJS(args={key:value for key,value in iterable2+[('radio',radio)]}, code=radiogroup_code)
    radio.js_on_change('active', callback2)

    # Put controls in a single element
    grids = WidgetBox(gridplot(plots, ncols=Ncols, plot_width=256, plot_height=256, sizing_mode = 'stretch_both'), name="grids")
    #grids = gridplot(plots, ncols=5)

    # def update_cols(attr, old, new):
    #     pass
    #
    # cols_slider = Slider(start=1, end=5, value=2, step=1, title="Number of Columns")
    # cols_slider.on_change("value", update_cols)

    controls = column(children=[WidgetBox(height=100), WidgetBox(Div(text='<h4>Layers</h4>'), radio), WidgetBox(height=100), WidgetBox(Div(text='<h4>Flags</h4>'),checkbox), WidgetBox(height=100), WidgetBox(Div(text='<h4>Feature</h4>'), size_slider)])


    #controls = column(radio, checkbox)


    #layout = column(Div(text='<h1>%s</h1>' %(title)), Div(text='<h3>%s</h3>' %(main_text)), row(column(Div(text='<h3>%s</h3>' %(buttons_text)), controls), grid))
    #show(layout)

    layout = column(row(controls, grids))

    return layout

#if __name__ == '__main__':

#get vars
args = curdoc().session_context.request.arguments

try:
    userfile_path = args.get('userfile_path')[0].decode("utf-8")  #pass this as a string
    if userfile_path == 'None':
        userfile_path = None
    print('userfile_path', userfile_path, type(userfile_path))
except:
    raise ValueError('no userfile_path')

try:
    reqPath = args.get('reqPath')[0].decode("utf-8")  #pass this as a string
    print('reqPath', reqPath, type(reqPath))
except:
    raise ValueError('no reqPath')

try:
    batchID = int(args.get('batchID')[0].decode("utf-8"))  #pass this as a string
    print('batchID', batchID, type(batchID))
except:
    raise ValueError('no batchID')

req = np.load(reqPath, allow_pickle=True).item()
data = np.load(req.get('catpath'))

if req.get('labels') is not None:
    veto = {key:data[val] for key, val in zip(req.get('labels').keys(), req.get('labels').values())}
else:
    veto = None

if req.get('info_list') is not None:
    info = {key:data[val] for key, val in zip(req.get('info_list').keys(), req.get('info_list').values())}
else:
    info = None

coord = [data[i] for i in req.get('coord_names')]
idx = req.get('%s_%s' %(req.get('room'), str(batchID)))
unclassified_label = ['UNCL']

if req.get('RGlabels') is not None:
    RGlabels = req.get('RGlabels') + unclassified_label
else:
    RGlabels = None

layer_list = req.get('layer_list')
Ncols = req.get('Ncols')
BoxSize = req.get('BoxSize')

for i in [req, data, veto, info, coord, idx, unclassified_label, RGlabels, layer_list, Ncols]:
    print(i, type(i))

#grid = [8,5]
savefile = None


#get scripts
layout = html_postages(coord=coord, idx=idx, veto=veto, info=info, layer_list=layer_list,
                       savefile=savefile, notebook=False,
                        RGlabels=RGlabels, output=None, userfile_path=userfile_path, Ncols=Ncols, BoxSize=BoxSize)

curdoc().add_root(layout)

