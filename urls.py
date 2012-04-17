#!/usr/bin/env python

__author__ = "Mike McCann"
__copyright__ = "Copyright 2012, MBARI"
__credits__ = ["Chander Ganesan, Open Technology Group"]
__license__ = "GPL"
__version__ = "$Revision: 12295 $".split()[1]
__maintainer__ = "Mike McCann"
__email__ = "mccann at mbari.org"
__status__ = "Development"
__doc__ = '''

The URL patterns for the stoqs database web application.  The first field specifies the
database that is automatically routed to the associated database defined in settings.py.


Mike McCann
MBARI Jan 3, 2012

@var __date__: Date of last svn commit
@undocumented: __doc__ parser
@author: __author__
@status: __status__
@license: __license__
'''

from django.conf.urls.defaults import *
from django.contrib.gis import admin
from django.conf import settings
##import views

admin.autodiscover()

# The database alias (the key of the DATABASES dictionary) will prefix all of our requests
pre = r'^(?P<dbAlias>[^/]+)/'  

# Repeated between clause for measurement queries
btwnCl = r'(?P<pName>[^/]+)/between/(?P<startDate>\w+)/(?P<endDate>\w+)/depth/(?P<dmin>[0-9\.]+)/(?P<dmax>[0-9\.]+)'

# type is one of: 'data', 'perf'; format is one of: 'html', 'csv', 'kml'
typePat = r'/(?P<type>[^/]{4,5})'
formatPat = r'(?P<format>[^/]{0,4})$'
formatCl = typePat + r'\.' + formatPat


urlpatterns = patterns('',
            
    # Admin interface
    url(pre + r'admin/', include(admin.site.urls)),

    # New Map interfaces with inheritence of bootstrap template
    url(pre + r'activityWMS$', 'stoqs.views.wms.showActivityWMS', {}, name='show-activity-wms'),

    # Map interfaces
    url(pre + r'activitiesWMS$', 'stoqs.views.wms.showActivitiesWMS', {}, name='show-activities-wms'),
    url(pre + r'parametersWMS$', 'stoqs.views.wms.showParametersWMS', {}, name='show-parameters-wms'),
    url(pre + r'platformsWMS$', 'stoqs.views.wms.showPlatformsWMS', {}, name='show-platforms-wms'),

    # All STOQS objects - full object queries with .json, .xml, .html, and .csv responses
    url(pre + r'platform.?'          + formatPat, 'stoqs.views.showPlatform',          {}, name='show-platform'),
    url(pre + r'platformType.?'      + formatPat, 'stoqs.views.showPlatformType',      {}, name='show-platformtype'),
    url(pre + r'parameter.?'         + formatPat, 'stoqs.views.showParameter',         {}, name='show-parameter'),
    url(pre + r'activity.?'          + formatPat, 'stoqs.views.showActivity',          {}, name='show-activity'),
    url(pre + r'activityType.?'      + formatPat, 'stoqs.views.showActivityType',      {}, name='show-activitytype'),
    url(pre + r'campaign.?'          + formatPat, 'stoqs.views.showCampaign',          {}, name='show-campaign'),
    url(pre + r'resource.?'          + formatPat, 'stoqs.views.showResource',          {}, name='show-resource'),
    url(pre + r'resourceType.?'      + formatPat, 'stoqs.views.showResourceType',      {}, name='show-resourcetype'),
    url(pre + r'activityresource.?'  + formatPat, 'stoqs.views.showActivityResource',  {}, name='show-activityresource'),
    url(pre + r'activityparameter.?' + formatPat, 'stoqs.views.showActivityParameter', {}, name='show-activityparameter'),
    url(pre + r'simpledepthtime.?'   + formatPat, 'stoqs.views.showSimpleDepthTime',   {}, name='show-simpledepthtime'),

    # Measurements  
    url(pre + 'measurement/' + btwnCl + formatCl, 
        'stoqs.views.measurement.showBetweenMeasurements', {}, name='show-between-meas'),
    url(pre + r'measurement/' + btwnCl + '/stride/(?P<stride>\d+)' + formatCl, 
        'stoqs.views.measurement.showBetweenMeasurements', {}, name='show-between-meas-stride'),
                       
    url(pre + 'measurement/sn/' + btwnCl + formatCl, 
        'stoqs.views.measurement.showBetweenMeasurements', {'snFlag': True}, name='show-between-sn-meas'),
    url(pre + r'measurement/sn/' + btwnCl + '/stride/(?P<stride>\d+)' + formatCl, 
        'stoqs.views.measurement.showBetweenMeasurements', {'snFlag': True}, name='show-between-sn-meas-stride'),
                       
    url(pre + r'measurement/' + btwnCl + '/count$', 
        'stoqs.views.measurement.showBetweenMeasurements', {'countFlag': True}, name='show-between-meas-count'),
    url(pre + r'measurement/sn/' + btwnCl + '/count$', 
        'stoqs.views.measurement.showBetweenMeasurements', {'countFlag': True, 'snFlag': True}, name='show-between-sn-meas-count'),
    ##(r'^measurementOfActivity/name/(?P<aName>\w+)/type/(?P<aType>\w+)/data.(?P<format>\w{0,4})$', views.showMeasurementsOfActivity),
    ##(r'^measurementOfActivity/name/(\w+)/type/(\w+)/stride/(\d+)/data.(\w{0,4})$', views.showMeasurementsOfActivity),

    # URL For Chander's STOQQManager related views
    url(pre + r'query/summary/$', 'stoqs.views.query.queryData', {}, name='stoqs-query-summary'),
    url(pre + r'query/(?P<format>[^/]+)/?$', 'stoqs.views.query.queryData', {}, name='stoqs-query-results'),
    url(pre + r'query/', 'stoqs.views.query.queryUI', {}, name='stoqs-query-ui'),

    # Management, etc.
    url(r'campaigns', 'stoqs.views.management.showCampaigns', {}, name='show-campaigns'),
    url(pre + r'mgmt$', 'stoqs.views.management.showDatabase', {}, name='show-database'),
    url(pre + r'deleteActivity/(?P<activityId>[0-9]+)$', 'stoqs.views.management.deleteActivity', {}, name='delete-activity'),
    url(pre + r'activitiesMBARICustom$', 'stoqs.views.management.showActivitiesMBARICustom', {}, name='show-activities'),

)

# Not to be used in Production.  Must start development server with --insecure option to run with DEBUG = False:
#    python manage.py runserver 0.0.0.0:8000 --insecure
if settings.DEBUG is False and settings.PRODUCTION is False:   #if DEBUG is True it will be served automatically
    urlpatterns += patterns('',
        url(r'^(?P<path>.*)$', 'django.contrib.staticfiles.views.serve', {'document_root': settings.STATIC_ROOT})
    )
