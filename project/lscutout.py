#
from functools import partial

import numpy as np

from bokeh.embed import components
from bokeh.models import ColumnDataSource, ImageURL, CustomJS, Span, OpenURL, TapTool
from bokeh.models.widgets import CheckboxGroup, RadioGroup
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


def html_postages(coord=None, idx=None, veto=None, info=None, layer_list=None, BoxSize=40):


    plots = {}
    sources = []
    layers = []

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


    for idx in idx_list:

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
        p.toolbar.logo = None
        p.toolbar_location = None
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

            ravpix, decvpix = coordtopix(center=[RAidx, DECidx], coord=[RA[(mask) & (val)], DEC[(mask) & (val)]], size=size, scale=scale)

            data = {}
            data['x'] = ravpix
            data['y'] = decvpix
            for info_key, info_val in zip(info.keys(), info.values()):
                data[info_key] = np.array(info_val)[(mask) & (val)]

            sourceCirc = ColumnDataSource(data=data)

            circle = p.circle('x', 'y', source=sourceCirc, size=15, fill_color=None, line_color=color, line_width=3)
            circle_i.append(circle)

        lineh = Span(location=size/2, dimension='height', line_color='white', line_dash='solid', line_width=1)
        linew = Span(location=size/2, dimension='width', line_color='white', line_dash='solid', line_width=1)

        p.add_layout(lineh)
        p.add_layout(linew)
        p.background_fill_color = "black"
        #p.outline_line_width = 15
        #p.outline_line_alpha = 0.7

        p.xgrid.grid_line_color = None
        p.ygrid.grid_line_color = None

        plots[str(idx)] = p

        sources.append(circle_i)
        layers.append(layers2)


    checkbox = CheckboxGroup(labels=list(veto.keys()), active=list(np.arange(len(veto))))
    iterable = [elem for part in [[('_'.join(['line',str(figid),str(lineid)]),line) for lineid,line in enumerate(elem)] for figid,elem in enumerate(sources)] for elem in part]
    checkbox_code = ''.join([elem[0]+'.visible=checkbox.active.includes('+elem[0].split('_')[-1]+');' for elem in iterable])
    callback = CustomJS(args={key:value for key,value in iterable+[('checkbox',checkbox)]}, code=checkbox_code)

    # print('===== plots ======')
    # print(checkbox_code)
    # print('====')
    # print({key:value for key,value in iterable+[('checkbox',checkbox)]})

    checkbox.js_on_click(callback)

    #script, div = components(plots)
    #print(div)

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


    # for key,val in zip(plots.keys(), plots.values()):
    #     print(key, '\t', val)

    #script, div = components(plots)
    #controls = WidgetBox(radio, checkbox)
    #plots['controls'] = components(radio)
    #script_2, div_2 = components(controls)

    print('===== plots ======')
    plots['checkbox'] = checkbox
    plots['radio'] = radio

    return components(plots)
