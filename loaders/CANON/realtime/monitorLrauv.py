#!/usr/bin/env python
__author__    = 'Mike McCann, Danelle Cline'
__version__ = '$Revision: $'.split()[1]
__date__ = '$Date: $'.split()[1]
__copyright__ = '2011'
__license__   = 'GPL v3'
__contact__   = 'mccann at mbari.org'
__doc__ = '''

Monitor the dods web site for new realtime hotspot or sbdlog data from LRAUVs and use
DAPloaders.py to load new data into the stoqs database.

Mike McCann
MBARI 12 March 2014

@var __date__: Date of last svn commit
@undocumented: __doc__ parser
@status: production
@license: GPL
'''

import os
import sys
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../toNetCDF"))      # lrauvNc4ToNetcdf.py is in sister toNetCDF dir
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))           # settings.py is two dirs up


import DAPloaders
from CANON import CANONLoader
import logging
import lrauvNc4ToNetcdf
from datetime import datetime, timedelta
import time
import re
from stoqs import models as mod
from pydap.client import open_url
from thredds_crawler.crawl import Crawl
from coards import from_udunits

# Set up global variables for logging output to STDOUT
logger = logging.getLogger('monitorTethysHotSpotLogger')
fh = logging.StreamHandler()
f = logging.Formatter("%(levelname)s %(asctime)sZ %(filename)s %(funcName)s():%(lineno)d %(message)s")
fh.setFormatter(f)
logger.addHandler(fh)
logger.setLevel(logging.DEBUG)

class NoNewHotspotData(Exception):
    pass

class NcFileMissing(Exception):
    def __init__(self, value):
        self.nc4FileUrl = value
    def __str__(self):
        return repr(self.nc4FileUrl)
  
def getNcStartEnd(urlNcDap):
    '''Find the lines in the html with the .nc file, then open it and read the start/end times
    return url to the .nc  and start/end as datetime objects.
    '''
    logger.debug('open_url on urlNcDap = %s', urlNcDap)
    df = open_url(urlNcDap)
    timeAxisName = 'depth_time'
    timeAxisUnits = df[timeAxisName].units
    if timeAxisUnits == 'seconds since 1970-01-01T00:00:00Z' or timeAxisUnits == 'seconds since 1970/01/01 00:00:00Z':
        timeAxisUnits = 'seconds since 1970-01-01 00:00:00'    # coards is picky

    startDatetime = from_udunits(df[timeAxisName][0][0], timeAxisUnits)
    endDatetime = from_udunits(df[timeAxisName][-1][0], timeAxisUnits)

    return startDatetime, endDatetime

def processDecimated(pw, url, outDir, lastDatetime, parms):
    '''
    Interpolate LRAUV data
    '''

    logger.debug('url = %s', url)
    outFile_i = os.path.join(outDir, url.split('/')[-1].split('.')[0] + '_i.nc')
    startDatetime, endDatetime = getNcStartEnd(url)
    logger.debug('startDatetime, endDatetime = %s, %s', startDatetime, endDatetime)
    logger.debug('lastDatetime = %s', lastDatetime)
    url_i = None
    if endDatetime > lastDatetime:
        logger.debug('Calling pw.process with outFile_i = %s', outFile_i)
        try:
            pw.process(url, outFile_i, parms)
        except TypeError as e:
            logger.warn('Problem reading data from %s', url)
            logger.warn('Assumming data are invalid and skipping')
        else:
            if outFile_i.startswith('/tmp'):
                # scp outFile_i to elvis, if unable to mount from elvis. Requires user to enter password.
                dir = '/'.join(url.split('/')[-7:-1])
                cmd = r'scp %s stoqsadm@elvis.shore.mbari.org:/mbari/LRAUV/%s' % (outFile_i, dir)
                print cmd
                os.system(cmd)

            url_i = url.replace('.nc4', '_i.nc')

    else:
        logger.debug('endDatetime <= lastDatetime. Assume that data from %s have already been loaded', url)

    return url_i, startDatetime, endDatetime
    
def process_command_line():
        '''
        The argparse library is included in Python 2.7 and is an added package for STOQS.
        '''
        import argparse
        from argparse import RawTextHelpFormatter

        examples = 'Examples:' + '\n\n'
        examples += 'Run on test database:\n'
        examples += sys.argv[0] + " -d  'Test Daphne hotspot data' -o /mbari/LRAUV/daphne/realtime/hotspotlogs -u 'http://elvis.shore.mbari.org/thredds/catalog/LRAUV/daphne/realtime/hotspotlogs' -b 'stoqs_canon_apr2014_t' -c 'CANON-ECOHAB - March 2014 Test'\n"    
        parser = argparse.ArgumentParser(formatter_class=RawTextHelpFormatter,
                                         description='Read lRAUV data transferred over hotstpot and .nc file in compatible CF1-6 Discrete Sampling Geometry for for loading into STOQS',
                                         epilog=examples)
                                             
        parser.add_argument('-u', '--inUrl',action='store', help='url where hotspot logs are - must be the same location as -o directory', default='.',required=True)   
        parser.add_argument('-b', '--database',action='store', help='name of database to load hotspot data to', default='.',required=True)  
        parser.add_argument('-c', '--campaign',action='store', help='name of campaign', default='.',required=True)    
        parser.add_argument('-o', '--outDir', action='store', help='output directory to store .nc file - must be the same location as -u URL', default='.',required=True)   
        parser.add_argument('-d', '--description', action='store', help='Brief description of experiment')
        parser.add_argument('-a', '--append', action='store_true', help='Append data to existing Activity')
        parser.add_argument('-v', '--verbose', action='store_true', help='Turn on verbose output')
   
        args = parser.parse_args()    
	return args

if __name__ == '__main__':
    colors = {  'tethys':       'fed976',
                'daphne':       'feb24c'}
  
    args = process_command_line()

    platformName = None; 

    # Base url for logs indicates what vehicle logs are being monitored 
    d = re.match(r'.*tethys*',args.inUrl) 
    if d:
        platformName = 'tethys'
    d = re.match(r'.*daphne*',args.inUrl)
    if d:
        platformName = 'daphne'

    if platformName is None:
        raise Exception('cannot find platformName from url %s' % args.inUrl)

    # Start back a week from now to load in old data
    lastDatetime = datetime.utcnow() - timedelta(days=7)
    
    # Assume that the database has already been created with description and terrain information, so use minimal arguments in constructor
    cl = CANONLoader(args.database, args.campaign)
    cl.dbAlias = args.database
    cl.campaignName = args.campaign
    parms = ['sea_water_temperature', 'sea_water_salinity', 'mass_concentration_of_chlorophyll_in_sea_water', 'voltage'] 
                     
    # Get directory list from sites
    logger.info("Crawling %s for shore.nc files" % (args.inUrl))
  
    c = Crawl(os.path.join(args.inUrl, 'catalog.xml'), select=[".*shore_\d+_\d+.nc4$"], debug=False)
    urls = [s.get("url") for d in c.datasets for s in d.services if s.get("service").lower() == "opendap"]

    pw = lrauvNc4ToNetcdf.InterpolatorWriter()

    # Look in time order - oldest to newest
    for url in sorted(urls):
        (url_i, startDatetime, endDatetime) = processDecimated(pw, url, args.outDir, lastDatetime, parms)
        lastDatetime = endDatetime

        if url_i:
            logger.info("Received new %s data ending at %s in %s" % (platformName, endDatetime, url_i))
            aName = platformName + '_sbdlog_' + startDatetime.strftime('%Y%m%dT%H%M%S')

            # Use Hyrax server to avoid the stupid caching that the TDS does
            url_i = url_i.replace('http://elvis.shore.mbari.org/thredds/dodsC/LRAUV', 'http://dods.mbari.org/opendap/data/lrauv')

            dataStartDatetime = None
            if args.append:
                # Return datetime of last timevalue - if data are loaded from multiple activities return the earliest last datetime value
                dataStartDatetime = InstantPoint.objects.using(self.dbAlias).filter(activity__name=aName).aggregate(Max('timevalue'))['timevalue__max']

            try:
                logger.debug("Instantiating Lrauv_Loader for url_i = %s", url_i)
                lrauvLoad = DAPloaders.runLrauvLoader(cName = args.campaign,
                                                      cDesc = None,
                                                      aName = aName,
                                                      aTypeName = 'LRAUV mission',
                                                      pName = platformName,
                                                      pTypeName = 'auv',
                                                      pColor = colors[platformName],
                                                      url = url_i,
                                                      parmList = parms,
                                                      dbAlias = args.database,
                                                      stride = 10,
                                                      startDatetime = startDatetime,
                                                      dataStartDatetime = dataStartDatetime,
                                                      endDatetime = endDatetime)

            except DAPloaders.NoValidData:
                logger.info("No measurements in this log set. Activity was not created as there was nothing to load.")
