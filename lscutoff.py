import numpy as np
import matplotlib.pyplot as plt
import os
import random

import bokeh.plotting as bk
from bokeh.models import ColumnDataSource, ImageURL, CustomJS, Span, OpenURL, TapTool, Panel, Tabs, Div
from bokeh.models.widgets import CheckboxGroup, CheckboxButtonGroup, RadioGroup, RadioButtonGroup
from bokeh.layouts import gridplot, row, column, WidgetBox
from bokeh.io import curdoc, show
from bokeh.embed import components
from bokeh.plotting import figure
from bokeh.resources import INLINE

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
                         buttons_text=None, RGlabels=None, output=None):

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
    tests = []
    js_resources_list = []
    css_resources_list = []
    script_list = []
    div_list = []

    if comparison is not None: a, b = comparison[0], comparison[1]

    RA, DEC = coord[0], coord[1]

    rows, cols = grid[0], grid[1]
    N = rows*cols
    scale_unit='pixscale'

    scale=0.262

    boxsize = 2*m*radius*3600
    size = int(round(boxsize/scale))
    print(boxsize, size)

    idx_list = random.sample(list(idx), rows*cols)

    if info is None:
        info = {'RA':RA, 'DEC':DEC}

    if veto is None:
        veto = {'all':np.ones_like(RA, dtype=bool)}

    if layer_list is None:

        layer_list = ['dr9f-south', 'dr9f-south-model', 'dr9f-south-resid', 'dr9g-south', 'dr9g-south-model', 'dr9g-south-resid',
                 'dr9f-north', 'dr9f-north-model', 'dr9f-north-resid', 'dr9g-north', 'dr9g-north-model', 'dr9g-north-resid']

#figlist = [figure(title='Figure '+str(i),plot_width=100,plot_height=100) for i in range(N)]

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

                #if info is not None:

                TOOLTIPS = []

                for key in info.keys():
                    TOOLTIPS.append((key, '@'+key))

            p = figure(plot_width=size, plot_height=size, tooltips=TOOLTIPS, tools="tap")
            p.axis.visible = False
            p.min_border = 0
            #if title is not None: p.title.text = title

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
            #test_i = []
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

                    #if info is not None:

                    data = {}
                    data['x'] = ravpix
                    data['y'] = decvpix
                    for info_key, info_val in zip(info.keys(), info.values()):
                        data[info_key] = info_val[(mask) & (val)]

                    sourceCirc = ColumnDataSource(data=data)

                circle = p.circle('x', 'y', source=sourceCirc, size=15, fill_color=None, line_color=color, line_width=3)
                circle_i.append(circle)

                #circletmp = p.circle('x', 'y', source=sourceCirc, size=30, fill_color=None, line_color=color, line_width=5)
                #test_i.append(circletmp)

            lineh = Span(location=size/2, dimension='height', line_color='white', line_dash='solid', line_width=1)
            linew = Span(location=size/2, dimension='width', line_color='white', line_dash='solid', line_width=1)

            p.add_layout(lineh)
            p.add_layout(linew)

            if RGlabels is not None:

                def my_radio_handler(new):
                    print('Radio button option ' + str(new) + ' selected.')

                rbt = RadioGroup(labels=RGlabels, active=len(RGlabels)-1, default_size=70)
                rbt.on_click(my_radio_handler)
                plots.append(WidgetBox(row(p, rbt)))
            else:
                plots.append(p)
            #plots.append(p)
            sources.append(circle_i)
            layers.append(layers2)
            #tests.append(test_i)

            # # grab the static resources
            # js_resources_list.append(INLINE.render_js())
            # css_resources_list.append(INLINE.render_css())
            # # render template
            # script, div = components(p)
            # script_list.append(script)
            # div_list.append(div)

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
    if tab:
        # Make a tab with the layout
        tab = Panel(child=layout, title = tab_title)
        return tab

    else:
        #grab the static resources
        js_resources = INLINE.render_js()
        css_resources = INLINE.render_css()
        script1, div1 = components(layout)
        #script2, div2 = components(column(controls))
        return js_resources, css_resources, script1, div1
        #return grid, controls
        #show(layout)


def bokeh():

    # init a basic bar chart:
    # http://bokeh.pydata.org/en/latest/docs/user_guide/plotting.html#bars
    fig = figure(plot_width=600, plot_height=600)
    fig.vbar(
        x=[1, 2, 3, 4],
        width=0.5,
        bottom=0,
        top=[1.7, 2.2, 4.6, 3.9],
        color='navy'
    )

    # grab the static resources
    js_resources = INLINE.render_js()
    css_resources = INLINE.render_css()

    # render template
    script, div = components(fig)

    return script, div, js_resources, css_resources
