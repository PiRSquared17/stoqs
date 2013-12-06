__author__    = 'Mike McCann'
__copyright__ = '2011'
__license__   = 'GPL v3'
__contact__   = 'mccann at mbari.org'

__doc__ = '''

View functions to supoprt the main query web page

@undocumented: __doc__ parser
@status: production
@license: GPL
'''

from django.shortcuts import render_to_response
from django.template import RequestContext
from django.http import HttpResponse, HttpResponseNotFound, HttpResponseBadRequest
from django.utils import simplejson
from django.conf import settings
from django.core import serializers
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db.utils import ConnectionDoesNotExist
from django.views.decorators.cache import cache_page
from utils.STOQSQManager import STOQSQManager
from utils import encoders
import json
import pprint
import csv


import logging 
from wms import ActivityView
from tempfile import NamedTemporaryFile
from utils.MPQuery import MPQuerySet

logger = logging.getLogger(__name__)

class InvalidMeasuredParameterQueryException(Exception):
    pass


class NoParameterSelectedException(Exception):
    pass

# Mapping from HTTP request parameters to what STOQSQueryManager needs
query_parms = {
                   'sampledparametersgroup': 'sampledparametersgroup',
                   'measuredparametersgroup': 'measuredparametersgroup',
                   'parameterstandardname': 'parameterstandardname',        
                   'parameterminmax': 'parameterminmax',    # Array of name, min, max
                   'time': ('start_time','end_time'),       # Single values
                   'depth': ('min_depth', 'max_depth'),     # Single values
                   'simpledepthtime': [],                   # List of x,y values
                   'platforms': 'platforms',                # Specified once in the query string for each platform.
                   'parametervalues': [],                   # Appended to below with any _MIN _MAX request items
                   'parameterparameter': ('px', 'py', 'pz', 'pc',               # Parameters to plot
                                          'xlog', 'ylog', 'zlog', 'clog'),      # Flags for log-scale

                    # TODO: Could simplify these flags by putting them into a dictionary...
                   'get_actual_count': 'get_actual_count',                                  # Flag value from checkbox
                   'showsigmatparametervalues': 'showsigmatparametervalues',                # Flag value from checkbox
                   'showstandardnameparametervalues': 'showstandardnameparametervalues',    # Flag value from checkbox
                   'showallparametervalues': 'showallparametervalues',                      # Flag value from checkbox
                   'showparameterplatformdata': 'showparameterplatformdata',                # Flag value from checkbox

                   'parameterplot': ('parameterplotid',                                     # Plot radio button selection
                                     'platformplotname'),                                   # - client knows platform name
                   'parametertimeplotid': 'parametertimeplotid',                            # Plot checkbox id values
                   'showgeox3ddata': 'showgeox3ddata',                                      # Flag value from checkbox
                   'showdataas': 'showdataas',              # Value from radio button, either 'contour' or 'scatter'

                   'only': 'only',                          # List of options to update - when only a partial response is needed
                   'parametertab': 'parametertab',          # = 1 if Parameter/Station tab is active and full resolution timeSeries data is needed
                   'secondsperpixel': 'secondsperpixel',    # Resolution of time-depth-flot window
                   'x3dterrains': 'x3dterrains',            # Hash of 3D Terrain info 
}

def get_http_site_uri(request):
    '''
    Override 'https' that gets put there with STOQS imbedded in the ODSS web app
    '''
    site_uri = request.build_absolute_uri('/')[:-1]
    site_uri = site_uri.replace('https', 'http')
    return site_uri

def _buildMapFile(request, qm, options):
    if 'platforms' not in json.loads(options):
        return

    # 'mappath' should be in the session from the call to queryUI() set it here in case it's not set by queryUI() 
    if request.session.has_key('mappath'):
        logger.info("Reusing request.session['mappath'] = %s", request.session['mappath'])
    else:
        request.session['mappath'] = NamedTemporaryFile(dir='/dev/shm', prefix=__name__, suffix='.map').name
        logger.info("Setting new request.session['mappath'] = %s", request.session['mappath'])

    # A rudumentary class of items for passing a list of them to the activity.map template
    class Item(object):
        def __repr__(self):
            return '%s %s %s %s' % (self.id, self.name, self.color, self.geo_query,)

    # Add an item (a mapfile layer) for each platform - unioned up
    item_list = []      # Replicates queryset from an Activity query (needs name & id) with added geo_query & color attrbutes

    trajectory_union_layer_string = ''
    for plats in json.loads(options)['platforms'].values():
        for p in plats:
            if p[3].lower() != 'trajectory':
                continue
            item = Item()
            item.id = p[1]
            item.name = p[0]
            trajectory_union_layer_string += str(item.name) + ','
            item.color = '"#%s"' % p[2]
            item.type = 'line'
            item.extra_style = ''
            item.geo_query = qm.getActivityGeoQuery(Q(platform__name='%s' % p[0]))
            item_list.append(item)

    station_union_layer_string = ''
    for plats in json.loads(options)['platforms'].values():
        for p in plats:
            if p[3].lower() != 'timeseries' and p[3].lower() != 'timeseriesprofile':
                continue
            item = Item()
            item.id = p[1]
            item.name = p[0]
            station_union_layer_string += str(item.name) + ','
            item.color = '"#%s"' % p[2]
            item.type = 'point'
            item.extra_style = 'SYMBOL "circle"\n        SIZE 7.0\n        OUTLINECOLOR 1 1 1'
            item.geo_query = qm.getActivityGeoQuery(Q(platform__name='%s' % p[0]), pointFlag=True)
            item_list.append(item)

    # Add an item for the samples for the existing query - do not add it to the union, it's a different type
    sample_geo_query = qm.getSampleGeoQuery()
    if sample_geo_query:
        item = Item()
        item.id = 'sample_points'
        item.name = 'sample_points'
        item.color = '255 255 255'
        item.type = 'point'
        item.geo_query = sample_geo_query
        item.extra_style = 'SYMBOL "circle"\n        SIZE 7.0\n        OUTLINECOLOR 0 0 0 '
        item_list.append(item)
    
    trajectory_union_layer_string = trajectory_union_layer_string[:-1]
    station_union_layer_string = station_union_layer_string[:-1]

    ##logger.debug('item_list = %s', pprint.pformat(item_list))        
    av = ActivityView(request, item_list, trajectory_union_layer_string, station_union_layer_string)
    av.generateActivityMapFile()

# Cache responses from this view for 15 minutes
@cache_page(60 * 15)
def queryData(request, format=None):
    '''
    Process data requests from the main query web page.  Returns both summary Activity and actual MeasuredParameter data
    as retreived from STOQSQManager.
    '''
    response = HttpResponse()
    params = {}
    for key, value in query_parms.iteritems():
        if type(value) in (list, tuple):
            params[key] = [request.GET.get(p, None) for p in value]
        else:
            params[key] = request.GET.getlist(key)

    # Look for any parameter _MIN & _MAX input from the UI.  After retrieving the above query_parms the
    # only thing left in the request QueryDict should be the parameter _MIN _MAX selections.
    for key, value in request.GET.iteritems():
        if key.endswith('_MIN'):                    # Just test for _MIN; UI will always provide _MIN & _MAX
            name = key.split('_MIN')[0]
            try:
                pminmax = {name: (request.GET.getlist(name + '_MIN')[0], request.GET.getlist(name + '_MAX')[0])}
            except:
                logger.exception('Could not get parameter values even though ' + key + ' ends with _MIN')
            params['parametervalues'].append(pminmax)
            logger.info('Adding to parametervalues: %s', pprint.pformat(pminmax))

    qm = STOQSQManager(request, response, request.META['dbAlias'])
    logger.debug('Calling buildQuerySets with params = %s', params)
    try:
        qm.buildQuerySets(**params)
    except ValidationError, e:
        logger.error(e)
        return HttpResponseBadRequest('Bad request: ' + str(e))
    try:
        options = simplejson.dumps(qm.generateOptions(),
                                   cls=encoders.STOQSJSONEncoder)
                                   # use_decimal=True) # After json v2.1.0 this can be used instead of the custom encoder class.
    except ConnectionDoesNotExist, e:
        logger.warn(e)
        return HttpResponseNotFound('The database alias <b>%s</b> does not exist on this server.' % request.META['dbAlias'])

    ##logger.debug('options = %s', pprint.pformat(options))
    ##logger.debug('len(simpledepthtime) = %d', len(json.loads(options)['simpledepthtime']))

    if not format: # here we export in a given format, or just provide summary data if no format is given.
        response['Content-Type'] = 'text/json'
        response.write(options)
    elif format == 'json':
        response['Content-Type'] = 'text/json'
        response.write(serializers.serialize('json', qm.qs))
    elif format == 'dap':
        logger.info('dap output')

    return response

# Do not cache this "view", it creates the mapfile
def queryMap(request):
    '''
    Build the mapfile in a separate view
    '''
    response = HttpResponse()
    params = {}
    for key, value in query_parms.iteritems():
        if type(value) in (list, tuple):
            params[key] = [request.GET.get(p, None) for p in value]
        else:
            params[key] = request.GET.getlist(key)

    # The Javascript the constructs the request items must remove any items that will make the 
    # server busy with requests that have nothing to do with making a map; for example, removing
    # 'parameterparameterpng' and 'parameterparameterx3d' removed from 'only' helps speed things up.

    qm = STOQSQManager(request, response, request.META['dbAlias'])
    logger.debug('Calling buildQuerySets with params = %s', params)
    qm.buildQuerySets(**params)
    options = simplejson.dumps(qm.generateOptions(),
                               cls=encoders.STOQSJSONEncoder)
    logger.debug('options = %s', pprint.pformat(options))
    _buildMapFile(request, qm, options)

    response['Content-Type'] = 'text/json'
    response.write(options)

    return response

# Do not cache this "view", otherwise the incrorrect mappath is used
def queryUI(request):
    '''
    Build and return main query web page
    '''

    ##request.session.flush()
    if request.session.has_key('mappath'):
        logger.info("Reusing request.session['mappath'] = %s", request.session['mappath'])
    else:
        request.session['mappath'] = NamedTemporaryFile(dir='/dev/shm', prefix=__name__, suffix='.map').name
        logger.info("Setting new request.session['mappath'] = %s", request.session['mappath'])

    # Use list of tuples to preserve order
    formats=[('kml', 'Keyhole Markup Language - click on icon to view in Google Earth', ),
             ('sql', 'Structured Query Language for PostgreSQL', ),
             ('stoqstoolbox', 'stoqstoolbox - work with the data in Matlab', ),
             ('json', 'JavaScript Object Notation', ),
             ('csv', 'Comma Separated Values', ),
             ('tsv', 'Tabbed Separated Values', ),
             ('html', 'Hyper Text Markup Language table', ),
            ]

    return render_to_response('stoqsquery.html', {'site_uri': request.build_absolute_uri('/')[:-1],
                                                  'http_site_uri': get_http_site_uri(request),
                                                  'formats': formats,
                                                  'mapserver_host': settings.MAPSERVER_HOST,
                                                  'mappath': request.session['mappath'],
                                                  'google_analytics_code': settings.GOOGLE_ANALYTICS_CODE,
                                                 }, 
                            context_instance=RequestContext(request))
