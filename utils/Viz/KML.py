import os
import sys
import time
import numpy
import settings
import logging
from stoqs import models as m
from django.db.models import Avg
from django.http import HttpResponse
import pprint

logger = logging.getLogger(__name__)

def readCLT(fileName):
    '''
    Read the color lookup table from disk and return a python list of rgb tuples.
    '''

    cltList = []
    for rgb in open(fileName, 'r'):
        ##logger.debug("rgb = %s", rgb)
        (r, g, b) = rgb.split('  ')[1:]
        cltList.append([float(r), float(g), float(b)])

    return cltList


class KML(object):
    '''
    Manage the construcion of KML files from stoqs.  Several options may be set on initialization and
    clients can get KML output with the kmlResponse() method.
    '''
    def __init__(self, request, qs_mp, qparams, **kwargs):
        '''
        Possible kwargs and their default values:
            @withTimeStamp: True
            @withLineStrings: True
        '''
        self.request = request
        self.qs_mp = qs_mp
        self.qparams = qparams

        logger.debug('request = %s', request)
        ##logger.debug('kwargs = %s', kwargs)
        logger.debug('qparams = %s', qparams)
        if 'withTimeStamp' in kwargs:
            self.withTimeStampFlag = kwargs['withTimeStamp']
        else:
            self.withTimeStampFlag = True

        if 'withLineStrings' in kwargs:
            self.withLineStringsFlag = kwargs['withLineStrings']
        else:
            self.withLineStringsFlag = True
            
        if 'withFullIconURL' in kwargs:
            self.withFullIconURLFlag = kwargs['withFullIconURL']
        else:
            self.withFullIconURLFlag = True

        if 'stride' in kwargs:
            # If passed in as an argument
            self.stride = kwargs['stride']
        else:
            # Check if in request, otherwise set it to 1
            self.stride = int(self.request.GET.get('stride', 1))

    def kmlResponse(self):
        '''
        Return a response that is a KML represenation of the existing MeasuredParameter query that is in self.qs_mp.
        pName is either the parameter__name or parameter__standard_name string.  Use @stride to return a subset of data.
        '''
        response = HttpResponse()
        if self.qs_mp is None:
            raise Exception('self.qs_mp is None.')
    
        # If both selected parameter__name takes priority over parameter__standard_name. If parameter__id supplied that takes overall precedence.
        pName = None
        if 'parameter__standard_name' in self.qparams:
            pName = self.qparams['parameter__standard_name']
        if 'parameter__name' in self.qparams:
            pName = self.qparams['parameter__name']
        if 'parameter__id' in self.qparams:
            logger.debug('parameter__id = %s', self.qparams['parameter__id'])
            pName = m.Parameter.objects.using(self.request.META['dbAlias']).get(id=int(self.qparams['parameter__id'])).name
            logger.debug('pName = %s', pName)
    
        if pName:
            logger.info("pName = %s", pName)
        else:
            raise Exception('parameter__name, parameter__standard_name, nor parameter__id specified')
    

        logger.debug('type(self.qs_mp) = %s', type(self.qs_mp))
        logger.debug('self.stride = %d', self.stride)

        try:
            # Expect the query set self.qs_mp to be a collection of value lists
            data = [(mp['measurement__instantpoint__timevalue'], mp['measurement__geom'].x, mp['measurement__geom'].y,
                     mp['measurement__depth'], mp['parameter__name'],  mp['datavalue'], mp['measurement__instantpoint__activity__platform__name'])
                     for mp in self.qs_mp[::self.stride]]
        except TypeError:
            # Otherwise expect self.qs_mp to be a collection of model instances
            data = [(mp.measurement.instantpoint.timevalue, mp.measurement.geom.x, mp.measurement.geom.y,
                     mp.measurement.depth, mp.parameter.name,  mp.datavalue, mp.measurement.instantpoint.activity.platform.name)
                     for mp in self.qs_mp[::self.stride]]

        dataHash = {}
        for d in data:
            try:
                dataHash[d[6]].append(d)
            except KeyError:
                dataHash[d[6]] = []
                dataHash[d[6]].append(d)

        try:
            folderName = "%s_%.1f_%.1f" % (pName, float(self.qparams['measurement__depth__gte']), float(self.qparams['measurement__depth__lte']))
        except KeyError:
            folderName = "%s_" % (pName,)
        descr = self.request.get_full_path().replace('&', '&amp;')
        logger.debug(descr)
        kml = self.makeKML(self.request.META['dbAlias'], dataHash, pName, folderName, descr, self.request.GET.get('cmin', None), self.request.GET.get('cmax', None))
        response['Content-Type'] = 'application/vnd.google-earth.kml+xml'
        response.write(kml)
        return response

    def makeKML(self, dbAlias, dataHash, pName, title, desc, cmin=None, cmax=None):
        '''
        Generate the KML for the point in mpList
        cmin and cmax are the color min and max 
        '''

        #
        # Define the color lookup table and the color limits from 2.5 and 97.5 percentiles for each variable
        #
        clt = readCLT(os.path.join(settings.STATIC_ROOT, 'colormaps', 'jetplus.txt'))
        climHash = {}
        for p in m.Parameter.objects.using(dbAlias).all().values_list('name'):
            pn = p[0]
            qs = m.ActivityParameter.objects.using(dbAlias).filter(parameter__name=pn).aggregate(Avg('p025'), Avg('p975'))
            climHash[pn] = (qs['p025__avg'], qs['p975__avg'],)
        logger.debug('Color lookup min, max values:\n' + pprint.pformat(climHash))


        pointKMLHash = {}
        lineKMLHash = {}
        if cmin and cmax:
            clim = (float(cmin), float(cmax),)
        else:
            clim = climHash[pName]
        logger.debug('clim = %s', clim)
    
        for k in dataHash.keys():
            (pointStyleKML, pointKMLHash[k]) = self._buildKMLpoints(k, dataHash[k], clt, clim)
            if self.withLineStringsFlag:
                (lineStyleKML, lineKMLHash[k]) = self._buildKMLlines(k, dataHash[k], clt, clim)
            else:
                logger.debug('Not drawing LineStrings for platform = %s', k)

        #
        # KML header
        #
        kml = '''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://earth.google.com/kml/2.1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://earth.google.com/kml/2.1 http://code.google.com/apis/kml/schema/kml21.xsd">
<!-- %s -->
<!-- Mike McCann MBARI 28 October 2010 -->
<Document>
<name>%s</name>
<description>%s</description>
''' % ('Automatically generated by views.py', title, desc)

        kml += pointStyleKML
        if self.withLineStringsFlag:
            kml += lineStyleKML

        #
        # See that the platforms are alphabetized in the KML.  (The point and line KMLHashes will have the same keys.)
        #
        platList = pointKMLHash.keys()
        platList.sort()
        for plat in platList:
            kml += '''<Folder>
<name>%s Points</name>
%s
</Folder>''' % (plat, pointKMLHash[plat])

            if self.withLineStringsFlag:
                kml += '''<Folder>
<name>%s Lines</name>
%s
</Folder>''' % (plat, lineKMLHash[plat])


        #
        # Footer
        #
        kml += '''</Document>
</kml>'''

        return kml

    def _buildKMLlines(self, plat, data, clt, clim):
        '''
        Build KML placemark LineStrings of all the point data in `list`
        Use distinctive line colors for each platform.
        the same way as is done in the auvctd dorado science data processing.
        `data` are the results of a query, say from xySlice()
        `clt` is a Color Lookup Table equivalent to a jetplus clt as used in Matlab
        `clim` is a 2 element list equivalent to clim in Matlab
    
        Return strings of style and point KML that can be included in a master KML file.
        '''

        styleKml = '''
<Style id="Tethys">
<LineStyle>
<color>ff0055ff</color>
<width>2</width>
</LineStyle>
</Style>
<Style id="Gulper_AUV">
<LineStyle>
<color>ff00ffff</color>
<width>2</width>
</LineStyle>
</Style>
<Style id="John Martin">
<LineStyle>
<color>ffffffff</color>
<width>1</width>
</LineStyle>
</Style>
'''

        #
        # Build the LineString for the points
        #
        lineKml = ''
        lastCoordStr = ''
        for row in data:
            (dt, lon, lat, depth, parm, datavalue, platform) = row

            if lat < -90 or lat > 90:
                # HACK warning: Fix any accidentally swapped lat & lons
                foo = lon
                lon = lat
                lat = foo

            coordStr = "%.6f,%.6f,-%.1f" % (lon, lat, depth)
    
            if lastCoordStr:
                if self.withTimeStampFlag:
                    placemark = """
<Placemark>
<styleUrl>#%s</styleUrl>
<TimeStamp>
<when>%s</when>
</TimeStamp>
<LineString>
<altitudeMode>absolute</altitudeMode>
<coordinates>
%s
</coordinates>
</LineString>
</Placemark> """         % (plat, time.strftime("%Y-%m-%dT%H:%M:%SZ", dt.timetuple()), lastCoordStr + ' ' + coordStr)
                else:
                    placemark = """
<Placemark>
<styleUrl>#%s</styleUrl>
<LineString>
<altitudeMode>absolute</altitudeMode>
<coordinates>
%s
</coordinates>
</LineString>
</Placemark> """         % (plat, lastCoordStr + ' ' + coordStr)

                lineKml += placemark

            lastCoordStr = coordStr

        return (styleKml, lineKml)

    def _buildKMLpoints(self, plat, data, clt, clim):
        '''
        Build KML Placemarks of all the point data in `list` and use colored styles 
        the same way as is done in the auvctd dorado science data processing.
        `data` are the results of a query, say from xySlice()
        `clt` is a Color Lookup Table equivalent to a jetplus clt as used in Matlab
        `clim` is a 2 element list equivalent to clim in Matlab

        Return strings of style and point KML that can be included in a master KML file.
        '''

        _debug = False

        #
        # Build the styles for the colors in clt using clim
        #
        if self.withFullIconURLFlag:
            baseURL = self.request.build_absolute_uri('/')[:-1] + '/' + settings.STATIC_URL
        else:
            baseURL = settings.STATIC_URL

        styleKml = ''
        for c in clt:
            ge_color = "ff%02x%02x%02x" % ((round(c[2] * 255), round(c[1] * 255), round(c[0] * 255)))
            if _debug:
                logger.debug("c = %s", c)
                logger.debug("ge_color = %s", ge_color)


            style = '''<Style id="%s">
<IconStyle>
<color>%s</color>
<scale>0.6</scale>
<Icon>
<href>%s.png</href>
</Icon>
</IconStyle>
</Style>
''' % (ge_color, ge_color, os.path.join(baseURL, 'colormaps', 'jetplus_dots', ge_color))

            styleKml += style

        #
        # Build the placemarks for the points
        #
        pointKml = ''
        for row in data:
            (dt, lon, lat, depth, parm, datavalue, platform) = row
    
            if lat < -90 or lat > 90:
                # HACK Warning: Fix any accidentally swapped lat & lons
                foo = lon
                lon = lat
                lat = foo

            coordStr = "%.6f, %.6f,-%.1f" % (lon, lat, depth)

            if _debug:
                logger.debug("datavalue = %f", float(datavalue))
                logger.debug("clim = %s", clim)

            clt_index = int(round((float(datavalue) - clim[0]) * ((len(clt) - 1) / float(numpy.diff(clim)))))
            if clt_index < 0:
                clt_index = 0;
            if clt_index > (len(clt) - 1):
                clt_index = int(len(clt) - 1);
            if _debug:
                logger.debug("clt_index = %d", clt_index)
            ge_color_val = "ff%02x%02x%02x" % ((round(clt[clt_index][2] * 255), round(clt[clt_index][1] * 255), round(clt[clt_index][0] * 255)))

            if self.withTimeStampFlag:
                placemark = """
<Placemark>
<styleUrl>#%s</styleUrl>
<TimeStamp>
<when>%s</when>
</TimeStamp>
<Point>
<altitudeMode>absolute</altitudeMode>
<coordinates>
%s
</coordinates>
</Point>
</Placemark> """         % (ge_color_val, time.strftime("%Y-%m-%dT%H:%M:%SZ", dt.timetuple()), coordStr)
            else:
                placemark = """
<Placemark>
<styleUrl>#%s</styleUrl>
<Point>
<altitudeMode>absolute</altitudeMode>
<coordinates>
%s
</coordinates>
</Point>
</Placemark> """         % (ge_color_val, coordStr)

            pointKml += placemark

        return (styleKml, pointKml)

