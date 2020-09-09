#
from functools import partial

import numpy as np
import os
import random
import pandas as pd

import bokeh.plotting as bk
from bokeh.models import ColumnDataSource, ImageURL, CustomJS, Span, OpenURL, TapTool, Div
from bokeh.models.widgets import CheckboxGroup, RadioGroup
from bokeh.layouts import gridplot, row, column, WidgetBox
from bokeh.io import curdoc, show
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


def html_postages(coord=None, idx=None, notebook=True, savefile=None, htmltitle='page', veto=None, info=None, grid=[2,2], m=4,
                      radius=4/3600, comparison=None, layer_list=None, title=None, tab=False, tab_title=None, main_text=None,
                         buttons_text=None, RGlabels=None, output=None, userfile_path=None):

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

    if userfile_path is not None:
        userfile = pd.read_csv(userfile_path + '.cvs')
        current_RGval = userfile['data']

    if RGlabels is not None:
        RGlabels_id = {key:i for i, key in enumerate(RGlabels)}

    def my_radio_handler(event, idx):
        print(event, RGlabels[event], idx)

        if userfile_path is not None:
            userfile = pd.read_csv(userfile_path + '.cvs')
            print(userfile_path)
            userfile.iloc[idx] = str(RGlabels[event])
            userfile.to_csv(userfile_path+'.cvs', index=False)

    if comparison is not None: a, b = comparison[0], comparison[1]

    RA, DEC = coord[0], coord[1]

    rows, cols = grid[0], grid[1]
    N = rows*cols
    scale_unit='pixscale'

    scale=0.262

    boxsize = 2*m*radius*3600
    size = int(round(boxsize/scale))
    print(boxsize, size)

    idx_list = idx#random.sample(list(idx), rows*cols)

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

            ramin, ramax = RAidx-m*radius, RAidx+m*radius
            decmin, decmax = DECidx-m*radius, DECidx+m*radius
            dra = (ramax - ramin)/40
            ddec = (decmax - decmin)/40
            mask = (RA > ramin + dra) & (RA < ramax - dra) & (DEC > decmin + ddec) & (DEC < decmax - ddec)


            if comparison is not None:

                TOOLTIPS = []
                for i in ['RA', 'DEC', 'morph', 'r', 'g', 'z', 'refcat']:
                    TOOLTIPS.append((i+'_b', '@'+i+'_b'))
                    TOOLTIPS.append((i+'_a', '@'+i+'_a'))
            else:

                TOOLTIPS = []

                for key in info.keys():
                    TOOLTIPS.append((key, '@'+key))

            p = figure(plot_width=size, plot_height=size, tooltips=TOOLTIPS, tools="tap")
            p.axis.visible = False
            p.min_border = 0

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

                ravpix, decvpix = coordtopix(center=[RAidx, DECidx], coord=[RA[(mask) & (val)], DEC[(mask) & (val)]], size=size, scale=scale)

                if comparison is not None:

                    sourceCirc = ColumnDataSource(data=dict(
                        x=ravpix,
                        y=decvpix,
                        r_b=cat['RMAG_%s' %(b)][(mask) & (val)], r_a=cat['RMAG_%s' %(a)][(mask) & (val)],
                        g_b=cat['GMAG_%s' %(b)][(mask) & (val)], g_a=cat['GMAG_%s' %(a)][(mask) & (val)],
                        z_b=cat['ZMAG_%s' %(b)][(mask) & (val)], z_a=cat['ZMAG_%s' %(a)][(mask) & (val)],
                        morph_b=cat['TYPE_%s' %(b)][(mask) & (val)], morph_a=cat['TYPE_%s' %(a)][(mask) & (val)],
                        refcat_b=cat['REF_CAT_%s' %(b)][(mask) & (val)], refcat_a=cat['REF_CAT_%s' %(a)][(mask) & (val)],
                        RA_b=cat['RA_%s' %(b)][(mask) & (val)], RA_a=cat['RA_%s' %(a)][(mask) & (val)],
                        DEC_b=cat['DEC_%s' %(b)][(mask) & (val)], DEC_a=cat['DEC_%s' %(a)][(mask) & (val)]
                        ))

                else:

                    data = {}
                    data['x'] = ravpix
                    data['y'] = decvpix
                    for info_key, info_val in zip(info.keys(), info.values()):
                        data[info_key] = info_val[(mask) & (val)]

                    sourceCirc = ColumnDataSource(data=data)

                circle = p.circle('x', 'y', source=sourceCirc, size=15, fill_color=None, line_color=color, line_width=3)
                circle_i.append(circle)

            lineh = Span(location=size/2, dimension='height', line_color='white', line_dash='solid', line_width=1)
            linew = Span(location=size/2, dimension='width', line_color='white', line_dash='solid', line_width=1)

            p.add_layout(lineh)
            p.add_layout(linew)

            if RGlabels is not None:
                print(current_RGval.iloc[idx], RGlabels_id[current_RGval.iloc[idx]])
                rbt = RadioGroup(labels=RGlabels, active=RGlabels_id[current_RGval.iloc[idx]], default_size=50)
                rbt.on_click(partial(my_radio_handler, idx=idx))
                plots.append(WidgetBox(row(p, rbt)))
            else:
                plots.append(p)

            sources.append(circle_i)
            layers.append(layers2)

    checkbox = CheckboxGroup(labels=list(veto.keys()), active=list(np.arange(len(veto))))
    iterable = [elem for part in [[('_'.join(['line',str(figid),str(lineid)]),line) for lineid,line in enumerate(elem)] for figid,elem in enumerate(sources)] for elem in part]
    checkbox_code = ''.join([elem[0]+'.visible=checkbox.active.includes('+elem[0].split('_')[-1]+');' for elem in iterable])
    callback = CustomJS(args={key:value for key,value in iterable+[('checkbox',checkbox)]}, code=checkbox_code)
    checkbox.js_on_click(callback)

    radio = RadioGroup(labels=layer_list, active=0)
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

    grid = gridplot(plots, ncols=cols, plot_width=256, plot_height=256, sizing_mode = 'stretch_both')

    # Put controls in a single element
    controls = column(WidgetBox(radio, checkbox), sizing_mode='fixed', css_classes=['scrollable'])

    if title is None: title = '--'
    if main_text is None: main_text = '...'
    if buttons_text is None: buttons_text = '...'

    layout = column(Div(text='<h1>%s</h1>' %(title)), Div(text='<h3>%s</h3>' %(main_text)), row(column(Div(text='<h3>%s</h3>' %(buttons_text)), controls), grid))
    #show(layout)
    return layout

#if __name__ == '__main__':

#get vars
args = curdoc().session_context.request.arguments

print(args)

try:
    catpath = args.get('catpath')[0]  #pass this as a string
except:
    cathpath = os.path.abspath(os.getcwd())+'/projects/_files/VITestFile.npy'

try:
    userfile_path = args.get('userfile_path')[0].decode("utf-8") #pass this as a string
except:
    userfile_path = None

try:
    idx = args.get('idx')[0].decode("utf-8") #pass this as a list
    idx = [int(i) for i in idx[1:-1].split()]
except:
    idx = None

try:
    labels = args.get('labels')[0] #pass labels as a dict
except:
    labels = {'BGS':'bgs', 'No BGS':'not_bgs'}

try:
    coord_names = args.get('coord_names')[0] #pass this as a list
except:
    coord_names = ['RA', 'DEC']

try:
    info_list = args.get('info_list')[0] #pass info as a list
except:
    info_list = ['RMAG', 'GMAG', 'ZMAG', 'TYPE']

try:
    layer_list = args.get('layer_list')[0] #pass this as a list
except:
    dr, survey = 'dr8', 'south'
    layer_list = ['%s-%s' %(dr, survey), '%s-%s-model' %(dr, survey), '%s-%s-resid' %(dr, survey)]

# try:
#     centre = args.get('centre')[0] #pass this as a string
# except:
#     centre = 'centre'

try:
    RGlabels = args.get('RGlabels')[0] #pass this as a list
except:
    RGlabels = ["STAR", "GAL", "CONT", "OTHR"]

data = np.load(cathpath)

print('========= idx ===========')
print(idx, type(idx))

# veto = {}
# for key, val in zip(labels.keys(), labels.values()):
#     veto[key] = data[val]
veto = {key:data[val] for key, val in zip(labels.keys(), labels.values())}
info = {key:data[key] for key in info_list}
info_list = info_list + coord_names
coord = [data[i] for i in coord_names]
if idx is None:
    idx = list(np.where(data['centre']))[0]
unclassified_label = ['UNCL']
RGlabels = RGlabels + unclassified_label
title = None
main_text = None
buttons_text = None
grid = [5,2]
savefile = None

print(cathpath)
print(data.dtype.names)
print(veto.keys())
print(info_list)
print(coord_names)
print(idx)
print(RGlabels)

print('userfile_path: \t %s' %(userfile_path))

#get scripts
layout = html_postages(coord=coord, idx=idx, veto=veto, info=info, grid=grid, layer_list=layer_list, title=title,
                  main_text=main_text, buttons_text=buttons_text, savefile=savefile, notebook=False,
                        RGlabels=RGlabels, output=None, userfile_path=userfile_path)

curdoc().add_root(layout)
#show(layout)
