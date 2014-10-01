#!/usr/bin/env python

__author__ = "Mike McCann"
__copyright__ = "Copyright 2014, MBARI"
__license__ = "GPL"
__maintainer__ = "Mike McCann"
__email__ = "mccann at mbari.org"
__status__ = "Development"
__doc__ = '''

Script produce products (plots, kml, etc.) to help understand drifting data.
- Make progressive vector diagram from moored ADCP data (read from STOQS)
- Plot drogued drifter, ship, and other data (read from Tracking DB)
- Plot sensor data (read from STOQS)

Output as a .png map, .kml file, or ...

Mike McCann
MBARI 22 September 2014

@var __date__: Date of last svn commit
@undocumented: __doc__ parser
@author: __author__
@status: __status__
@license: __license__
'''

import os
import sys
os.environ['DJANGO_SETTINGS_MODULE']='settings'
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))  # settings.py is one dir up

import csv
import time
import pyproj
import urllib2
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pytz 
from datetime import datetime
from collections import defaultdict
from stoqs.models import MeasuredParameter, NominalLocation
from django.http import HttpRequest
from utils.Viz.KML import KML
from mpl_toolkits.basemap import Basemap


class Drift():
    '''Data and methods to support drift data product preparation
    '''
    trackDrift = defaultdict(lambda: {'es': [], 'lon': [], 'lat': []})        # To be keyed by platform name
    adcpDrift = defaultdict(lambda: {'es': [], 'lon': [], 'lat': []})       # To be keyed by depth

    def loadTrackingData(self):
        '''Fill up trackDrift dictionary
        '''
        for url in self.args.trackData:
            # Careful - trackingdb returns the records in reverse time order
            for r in csv.DictReader(urllib2.urlopen(url)):
                # Use logic to skip inserting values if one or the other or both start and end are specified
                if self.startDatetime:
                    if datetime.utcfromtimestamp(float(r['epochSeconds'])) < self.startDatetime:
                        continue
                if self.endDatetime:
                    if datetime.utcfromtimestamp(float(r['epochSeconds'])) > self.endDatetime:
                        continue

                self.trackDrift[r['platformName']]['es'].insert(0, float(r['epochSeconds']))
                self.trackDrift[r['platformName']]['lat'].insert(0, float(r['latitude']))
                self.trackDrift[r['platformName']]['lon'].insert(0, float(r['longitude']))

    def computeADCPDrift(self):
        '''Read data from database and put computed progressive vectors into adcpDrift dictionary
        '''
        if self.args.adcpPlatform:
            adcpQS = MeasuredParameter.objects.using(self.args.database).filter(
                                measurement__instantpoint__activity__platform__name=self.args.adcpPlatform)

        if self.startDatetime:
            adcpQS = adcpQS.filter(measurement__instantpoint__timevalue__gte=self.startDatetime)
        if self.endDatetime:
            adcpQS = adcpQS.filter(measurement__instantpoint__timevalue__lte=self.endDatetime)

        if self.args.adcpMinDepth:
            adcpQS = adcpQS.filter(measurement__depth__gte=self.args.adcpMinDepth)
        if self.args.adcpMaxDepth:
            adcpQS = adcpQS.filter(measurement__depth__lte=self.args.adcpMaxDepth)

        utd = adcpQS.filter(parameter__standard_name='eastward_sea_water_velocity').values_list(
                                'datavalue', 'measurement__instantpoint__timevalue', 'measurement__depth').order_by(
                                        'measurement__depth', 'measurement__instantpoint__timevalue')
        vtd = adcpQS.filter(parameter__standard_name='northward_sea_water_velocity').values_list(
                                'datavalue', 'measurement__instantpoint__timevalue', 'measurement__depth').order_by(
                                        'measurement__depth', 'measurement__instantpoint__timevalue')

        # Compute positions (progressive vectors) - horizontal displacement in meters
        x = defaultdict(lambda: [])
        y = defaultdict(lambda: [])
        last_udiff = None
        for i, ((u, ut, ud), (v, vt, vd)) in enumerate(zip(utd, vtd)):
            try:
                udiff = utd[i+1][1] - ut
                vdiff = vtd[i+1][1] - vt
            except IndexError as e:
                # Extrapolate using last time difference, assuming it's regular and that we are at the last point, works only for very last point
                udiff = last_udiff
                vdiff = last_udiff
            else:
                last_udiff = udiff
                
            if udiff != vdiff:
                raise Exception('udiff != vdiff')
            else:
                dt = udiff.seconds + udiff.days * 24 * 3600

            if dt < 0:
                # For intermediate depths where (utd[i+1][1] - ut) is a diff with the time of the next depth
                dt = last_dt

            if ud != vd:
                raise Exception('ud != vd')
            else:
                x[ud].append(u * dt / 100)
                y[vd].append(v * dt / 100)
                self.adcpDrift[ud]['es'].append(time.mktime(ut.timetuple()))
                last_dt = dt

        # Work in UTM space to add x & y offsets to begining position of the mooring
        g0 = NominalLocation.objects.using(self.args.database).filter(activity__platform__name=self.args.adcpPlatform).values_list('geom')[0][0]
        p = pyproj.Proj(proj='utm', zone=10, ellps='WGS84')
        e0, n0 = p(g0.x, g0.y) 
        for depth in x:
            eList = np.cumsum([e0] + x[depth])
            nList = np.cumsum([n0] + y[depth])
            lonList, latList = p(eList, nList, inverse=True)
            self.adcpDrift[depth]['lon'] = lonList
            self.adcpDrift[depth]['lat'] = latList
    
    def process(self):
        '''Read in data and build structures that we can generate products from
        '''
        if self.args.trackData:
            self.loadTrackingData()

        if self.args.adcpPlatform:
            self.computeADCPDrift()

    def getExtent(self):
        '''For all data members find the min and max latitude and longitude
        '''
        if self.args.extent:
            return self.args.extent
        else:
            lonMin = 180
            lonMax = -180
            latMin = 90
            latMax = -90
            for drift in (self.trackDrift, self.adcpDrift):
                for k,v in drift.iteritems():
                    if np.min(v['lon']) < lonMin:
                        lonMin = np.min(v['lon'])
                    if np.max(v['lon']) > lonMax:
                        lonMax = np.max(v['lon'])
                    if np.min(v['lat']) < latMin:
                        latMin = np.min(v['lat'])
                    if np.max(v['lat']) > latMax:
                        latMax = np.max(v['lat'])

            # Expand the computed extent by extendDeg degrees
            extendDeg = self.args.extend
            return lonMin - extendDeg, latMin - extendDeg, lonMax + extendDeg, latMax + extendDeg

    def createPNG(self, fileName=None, forGeotiff=False):
        '''Draw processed data on a map and save it as a .png file
        '''
        if not forGeotiff:
            fig = plt.figure(figsize=(9, 6))
        else:
            fig = plt.figure()

        if not forGeotiff:
            ax = plt.axes()
        else:
            ax = plt.axes([0,0,1,1])

        if not fileName:
            fileName = self.args.pngFileName

        e = self.getExtent() 
        m = Basemap(llcrnrlon=e[0], llcrnrlat=e[1], urcrnrlon=e[2], urcrnrlat=e[3], projection='cyl', resolution='l', ax=ax)
        if not forGeotiff:
            m.arcgisimage(server='http://services.arcgisonline.com/ArcGIS', service='Ocean_Basemap')

        for depth, drift in self.adcpDrift.iteritems():
            m.plot(drift['lon'], drift['lat'], '-', c='black', linewidth=1)
            plt.text(drift['lon'][-1], drift['lat'][-1], '%i m' % depth, size='small')

        for platform, drift in self.trackDrift.iteritems():
            # Ad hoc coloring of platforms...
            if platform.startswith('stella'):
                color = 'yellow'
            elif platform.startswith('daphne'):
                color = 'orange'
            else:
                color = 'red'

            m.plot(drift['lon'], drift['lat'], '-', c=color, linewidth=2)
            plt.text(drift['lon'][-1], drift['lat'][-1], platform, size='small')

        if not forGeotiff:
            m.drawparallels(np.linspace(e[1],e[3],num=3), labels=[True,False,False,False], linewidth=0)
            m.drawmeridians(np.linspace(e[0],e[2],num=3), labels=[False,False,False,True], linewidth=0)
            try:
                plt.title(self.title)
            except AttributeError:
                pass
            fig.savefig(fileName)
            print 'Wrote file', self.args.pngFileName
        else:
            plt.axis('off')
            try:
                plt.text(0.5, 0.95, self.title, horizontalalignment='center', verticalalignment='top', transform=ax.transAxes)
            except AttributeError:
                pass
            fig.savefig(fileName, transparent=True, dpi=300)

        plt.clf()
        plt.close()

    def createGeoTiff(self):
        '''Your image must be only the geoplot with no decorations like axis titles, axis labels, etc., and you 
        will need accurate upper-left and lower-right coordinates in EPSG:4326 projection, also known as WGS 84 projection,...

        The syntax is pretty straightforward, something like the following will convert your image to the correct format:

            gdal_translate <image.png> <image.tiff> -a_ullr -122.25 37.1 -121.57365 36.67558 

        There is also a python wrapper for the GDAL library
 
        https://pypi.python.org/pypi/GDAL/
        '''

        e = self.getExtent()
        self.createPNG(self.args.geotiffFileName + '.png', forGeotiff=True)
        cmd = 'gdal_translate %s %s -a_ullr %s %s %s %s' % (self.args.geotiffFileName + '.png', 
                                                            self.args.geotiffFileName, e[0], e[3], e[2], e[1])
        print "Executing:\n", cmd
        os.system(cmd)
        os.remove(self.args.geotiffFileName + '.png')
        print 'Wrote file', self.args.geotiffFileName

    def createKML(self):
        '''Reuse STOQS utils/Viz code to build some simple KML. Use 'position' for Parameter Name.
        Fudge data value to distinguish platforms by color, use 0.0 for depth except for adcp data.
        '''
        request = HttpRequest()
        qs = None
        qparams = {}
        stoqs_object_name = None
        kml = KML(request, qs, qparams, stoqs_object_name, withTimeStamps=True, withLineStrings=True, withFullIconURL=True)

        # Put data into form that KML() expects - use different datavalues (-1, 1) to color the platforms
        dataHash = defaultdict(lambda: [])  
        colors = {}
        values = np.linspace(-1, 1, len(self.trackDrift.keys()))
        for i, k in enumerate(self.trackDrift.keys()):
            colors[k] = values[i]

        for platform, drift in self.trackDrift.iteritems():
            for es, lo, la in zip(drift['es'], drift['lon'], drift['lat']):
                dataHash[platform].append([datetime.utcfromtimestamp(es), lo, la, 0.0, 'position', colors[platform], platform])

        for depth, drift in self.adcpDrift.iteritems():
            for es, lo, la in zip(drift['es'], drift['lon'], drift['lat']):
                dataHash[depth].append([datetime.utcfromtimestamp(es), lo, la, float(depth), 'position', 0.0, 'adcp'])

        try:
            title = self.title
        except AttributeError:
            title = 'Product of STOQS drift_data.py'
        kml = kml.makeKML(self.args.database, dataHash, 'position', title, self.commandline, 0.0, 0.0 )

        fh = open(self.args.kmlFileName, 'w')
        fh.write(kml)
        fh.close()
        print 'Wrote file', self.args.kmlFileName

    def process_command_line(self):
        '''The argparse library is included in Python 2.7 and is an added package for STOQS.
        '''
        import argparse
        from argparse import RawTextHelpFormatter

        examples = 'Examples:' + '\n\n' 
        examples += "M1 ADCP progressive vector diagram and Stella and Rachel Carson position data:\n"
        examples += sys.argv[0] + " --database stoqs_september2014 --adcpPlatform M1_Mooring --adcpMinDepth 30 --adcpMaxDepth 40"
        examples += " --trackData http://odss.mbari.org/trackingdb/position/stella101/between/20140922T171500/20141010T000000/data.csv"
        examples += " http://odss.mbari.org/trackingdb/position/R_CARSON/between/20140922T171500/20141010T000000/data.csv"
        examples += " http://odss.mbari.org/trackingdb/position/stella122/between/20140922T171500/20141010T000000/data.csv"
        examples += " --pngFileName foo.png --start 20140923T180000 --end 20140925T150000"
        examples += "\n"
        examples += '\nIf running from cde-package replace ".py" with ".py.cde" in the above list.'
    
        parser = argparse.ArgumentParser(formatter_class=RawTextHelpFormatter,
                                         description='Script to produce products to help understand drift caused by currents in the ocean',
                                         epilog=examples)
                                             
        parser.add_argument('-d', '--database', action='store', help='Database alias', default='stoqs_september2014')

        parser.add_argument('--adcpPlatform', action='store', help='STOQS Platform Name for ADCP data')
        parser.add_argument('--adcpMinDepth', action='store', help='Minimum depth of ADCP data for progressive vector data', type=float)
        parser.add_argument('--adcpMaxDepth', action='store', help='Maximum depth of ADCP data for progressive vector data', type=float)

        parser.add_argument('--trackData', action='store', help='List of MBARItracking database .csv urls for data from drifters, ships, etc.', nargs='*', default=[])
    
        parser.add_argument('--start', action='store', help='Start time in YYYYMMDDTHHMMSS format')
        parser.add_argument('--end', action='store', help='End time in YYYYMMDDTHHMMSS format')
        parser.add_argument('--extend', action='store', help='Extend the data extent for the map boundaries by this value in degrees', default=0.05, type=float)
        parser.add_argument('--extent', action='store', help='Space separated specific map boundary in degrees: ll_lon ll_lat ur_lon ur_lat', nargs='*', type=float)

        parser.add_argument('--title', action='store', help='Title for plots, will override default title created if --start specified')
        parser.add_argument('--kmlFileName', action='store', help='Name of file for KML output')
        parser.add_argument('--pngFileName', action='store', help='Name of file for PNG image of map')
        parser.add_argument('--geotiffFileName', action='store', help='Name of file for geotiff image of map')

        parser.add_argument('-v', '--verbose', nargs='?', choices=[1,2,3], type=int, help='Turn on verbose output. Higher number = more output.', const=1)
    
        self.args = parser.parse_args()
        self.commandline = ' '.join(sys.argv)

        utc = pytz.utc
        self.startDatetime = None
        # Make both naiive and timezone aware datetime data members
        if self.args.start:
            self.startDatetime = datetime.strptime(self.args.start, '%Y%m%dT%H%M%S')
            self.startDatetimeUTC = utc.localize(self.startDatetime)
            self.startDatetimeLocal = self.startDatetimeUTC.astimezone(pytz.timezone('America/Los_Angeles'))
            self.title = 'Drift since %s' % self.startDatetimeLocal
        self.endDatetime = None
        if self.args.end:
            self.endDatetime = datetime.strptime(self.args.end, '%Y%m%dT%H%M%S')
            self.endDatetimeUTC = utc.localize(self.endDatetime)
            self.endDatetimeLocal = self.endDatetimeUTC.astimezone(pytz.timezone('America/Los_Angeles'))

        if self.args.title:
            self.title = self.args.title
    
    
if __name__ == '__main__':

    d = Drift()
    d.process_command_line()

    d.process()

    if d.args.pngFileName:
        d.createPNG()

    if d.args.geotiffFileName:
        d.createGeoTiff()

    if d.args.kmlFileName:
        d.createKML()

