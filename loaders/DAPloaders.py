#!/usr/bin/env python

__author__ = "Mike McCann"
__copyright__ = "Copyright 2011, MBARI"
__credits__ = ["Chander Ganesan, Open Technology Group"]
__license__ = "GPL"
__version__ = "$Revision: 1.1 $".split()[1]
__maintainer__ = "Mike McCann"
__email__ = "mccann at mbari.org"
__status__ = "Development"
__doc__ = '''

The DAPloaders module contains classes for reading data from OPeNDAP servers and
loading into the STOQS database.  It assumes that all data are on the 4 spatial-
temporal dimensions as defined in the COARDS/CF convention.  There are custom
derived classes here that understand, Mooring (Station and StationProfile), AUV 
and Glider (Trajectory) CDM Data Types.

Mike McCann
MBARI Dec 29, 2011

@var __date__: Date of last svn commit
@undocumented: __doc__ parser
@author: __author__
@status: __status__
@license: __license__
'''

# Force lookup of models to THE specific stoqs module.
import os
import sys
from django.contrib.gis.geos import GEOSGeometry, LineString, Point
os.environ['DJANGO_SETTINGS_MODULE']='settings'
project_dir = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../"))  # settings.py is one dir up
from django.conf import settings

from django.db.utils import IntegrityError, DatabaseError
from django.db import connection, transaction
from stoqs import models as m
from datetime import datetime, timedelta
from django.core.exceptions import ObjectDoesNotExist
from pydap.client import open_url
import pydap.model
import time
from decimal import Decimal
import math, numpy
from coards import to_udunits, from_udunits, ParserError
import csv
import urllib2
import logging
import socket
import seawater.csiro as sw
from utils.utils import percentile, median, mode, simplify_points
from loaders import STOQS_Loader, SkipRecord, missing_value, MEASUREDINSITU
import numpy as np


# Set up logging
logger = logging.getLogger('__main__')
logger.setLevel(logging.INFO)

# When settings.DEBUG is True Django will fill up a hash with stats on every insert done to the database.
# "Monkey patch" the CursorWrapper to prevent this.  Otherwise we can't load large amounts of data.
# See http://stackoverflow.com/questions/7768027/turn-off-sql-logging-while-keeping-settings-debug
from django.db.backends import BaseDatabaseWrapper
from django.db.backends.util import CursorWrapper

if settings.DEBUG:
    BaseDatabaseWrapper.make_debug_cursor = lambda self, cursor: CursorWrapper(cursor, self)


class ParameterNotFound(Exception): 
    pass


class NoValidData(Exception): 
    pass


class AuxCoordMissingStandardName(Exception):
    pass


class VariableMissingCoordinatesAttribute(Exception):
    pass


class Base_Loader(STOQS_Loader):
    '''
    A base class for data load operations.  This shouldn't be instantiated directly,
    instead a loader for a particular platform should inherit from it.  Since 
    each platform could have its own parameters, etc. each platform (at a minimum) 
    should declare the overridden names, ignored names, etc..
    The time bounds of an Activities can be specified in two ways:
    1. By specifying startDatetime and endDatetime.  This is handy for extracting a subset
       of data from an OPeNDAP data source, e.g. aggregated Mooring data, to populate a
       campaign specific database
    2. By setting startDatetime and endDatetime to None, in which case the start and end
       times are defined by the start and end of the data in the specified url

    A third time parameter (dataStartDatetime) can be specified.  This is used for when
    data is to be appended to an existing activity, such as for the realtime tethys loads
    as done by the monitorTethys.py script in the MBARItracking/sensortracks folder.  This
    use has not been fully tested.
    '''
    parameter_dict={} # used to cache parameter objects 
    standard_names = {} # should be defined for each child class
    include_names=[] # names to include, if set it is used in conjunction with ignored_names
    # Note: if a name is both in include_names and ignored_names it is ignored.
    ignored_names=[]  # Should be defined for each child class
    global_ignored_names = ['longitude','latitude', 'time', 'Time',
                'LONGITUDE','LATITUDE','TIME', 'NominalDepth', 'esecs', 'Longitude', 'Latitude',
                'DEPTH','depth'] # A list of parameters that should not be imported as parameters
    global_dbAlias = ''
    def __init__(self, activityName, platformName, url, dbAlias='default', campaignName=None, campaignDescription=None,
                activitytypeName=None, platformColor=None, platformTypeName=None, 
                startDatetime=None, endDatetime=None, dataStartDatetime=None, auxCoords=None, stride=1,
                grdTerrain=None ):
        '''
        Given a URL open the url and store the dataset as an attribute of the object,
        then build a set of standard names using the dataset.
        The activity is saved, as all the data loaded will be a set of instantpoints
        that use the specified activity.
        stride is used to speed up loads by skipping data.
        
        @param activityName: A string describing this activity
        @param platformName: A string that is the name of the platform. If that name for a Platform exists in the DB, it will be used.
        @param platformColor: An RGB hex string represnting the color of the platform. 
        @param url: The OPeNDAP URL for the data source
        @param dbAlias: The name of the database alias as defined in settings.py
        @param campaignName: A string describing the Campaign in which this activity belongs, If that name for a Campaign exists in the DB, it will be used.
        @param campaignDescription: A string expanding on the campaignName. It should be a short phrase expressing the where and why of a campaign.
        @param activitytypeName: A string such as 'mooring deployment' or 'AUV mission' describing type of activity, If that name for a ActivityType exists in the DB, it will be used.
        @param platformTypeName: A string describing the type of platform, e.g.: 'mooring', 'auv'.  If that name for a PlatformType exists in the DB, it will be used.
        @param startDatetime: A Python datetime.dateime object specifying the start date time of data to load
        @param endDatetime: A Python datetime.dateime object specifying the end date time of data to load
        @param dataStartDatetime: A Python datetime.dateime object specifying the start date time of data to append to an existing Activity
        @param auxCoords: a dictionary of coordinate standard_names (time, latitude, longitude, depth) pointing to exact names of those coordinates. Used for variables missing the coordinates attribute.
        @param stride: The stride/step size used to retrieve data from the url.
        '''
        self.campaignName = campaignName
        self.campaignDescription = campaignDescription
        self.activitytypeName = activitytypeName
        self.platformName = platformName
        self.platformColor = platformColor
        self.dbAlias = dbAlias
        global_dbAlias = dbAlias
        self.platformTypeName = platformTypeName
        self.activityName = activityName
        self.startDatetime = startDatetime
        self.endDatetime = endDatetime
        self.dataStartDatetime = dataStartDatetime  # For when we append data to an existing Activity
        self.auxCoords = auxCoords
        self.stride = stride
        self.grdTerrain = grdTerrain
        
        self.url = url
        self.varsLoaded = []
        try:
            self.ds = open_url(url)
        except socket.error,e:
            logger.error('Failed in attempt to open_url(%s)', url)
            raise e

        self.ignored_names += self.global_ignored_names # add global ignored names to platform specific ignored names.
        self.build_standard_names()

    def _getStartAndEndTimmeFromDS(self):
        '''
        Examine all possible time coordinates for include_names and set the overall min and max time for the dataset.
        To be used for setting Activity startDatetime and endDatetime.
        '''
        minDT = {}
        maxDT = {}
        for v in self.include_names:
            try:
                ac = self.getAuxCoordinates(v)
            except ParameterNotFound, e:
                logger.warn(e)
                continue

            if self.getFeatureType() == 'trajectory': 
                logger.debug('Getting trajectory min and max times for v = %s', v)
                logger.debug("self.ds[ac['time']][0] = %s", self.ds[ac['time']][0])
                try:
                    minDT[v] = from_udunits(self.ds[ac['time']][0][0], self.ds[ac['time']].attributes['units'])
                    maxDT[v] = from_udunits(self.ds[ac['time']][-1][0], self.ds[ac['time']].attributes['units'])
                except ParserError, e:
                    logger.warn("%s. Trying to fix up time units", e)
                    # Tolerate units like 1970-01-01T00:00:00Z - which is found on the IOOS Glider DAC
                    if self.ds[ac['time']].attributes['units'] == 'seconds since 1970-01-01T00:00:00Z':
                        minDT[v] = from_udunits(self.ds[ac['time']][0][0], 'seconds since 1970-01-01 00:00:00')
                        maxDT[v] = from_udunits(self.ds[ac['time']][-1][0], 'seconds since 1970-01-01 00:00:00')
                    
            elif self.getFeatureType() == 'timeseries' or self.getFeatureType() == 'timeseriesprofile': 
                logger.debug('Getting timeseries start time for v = %s', v)
                minDT[v] = from_udunits(self.ds[v][ac['time']][0][0], self.ds[ac['time']].attributes['units'])
                maxDT[v] = from_udunits(self.ds[v][ac['time']][-1][0], self.ds[ac['time']].attributes['units'])

        logger.debug('minDT = %s', minDT)
        logger.debug('maxDT = %s', maxDT)

        for v, dt in minDT.iteritems():
            try:
                if dt < startDatetime:
                    startDatetime = dt
            except NameError:
                startDatetime = dt
                
        for v, dt in maxDT.iteritems():
            try:
                if dt > endDatetime:
                    endDatetime = dt
            except NameError:
                endDatetime = dt
    
        logger.info('Activity startDatetime = %s, endDatetime = %s', startDatetime, endDatetime)            

        return startDatetime, endDatetime 


    def initDB(self):
        '''
        Do the intial Database activities that are required before the data are processed: getPlatorm and createActivity.
        Can be overridden by sub class.  An overriding method can do such things as setting startDatetime and endDatetime.
        '''
        if self.checkForValidData():
            self.platform = self.getPlatform(self.platformName, self.platformTypeName)
            self.addParameters(self.ds)

            # Ensure that startDatetime and startDatetime are defined as they are required fields of Activity
            if not self.startDatetime or not self.endDatetime:
                self.startDatetime, self.endDatetime = self._getStartAndEndTimmeFromDS()
            self.createActivity()
        else:
            raise NoValidData('No valid data in url %s' % (self.url))

    def getmissing_value(self, var):
        '''
        Return the missing_value attribute for netCDF variable var
        '''
        try:
            mv = self.ds[var].attributes['missing_value']
        except KeyError:
            logger.debug('Cannot get attribute missing_value for variable %s from url %s', var, self.url)
        else:
            return mv

    def get_FillValue(self, var):
        '''
        Return the _FillValue attribute for netCDF variable var
        '''
        try:
            fv = self.ds[var].attributes['_FillValue']
        except KeyError:
            logger.debug('Cannot get attribute _FillValue for variable %s from url %s', var, self.url)
            try:
                # Fred's L_662 and other glider data files have the 'FillValue' attribute, not '_FillValue'
                fv = self.ds[var].attributes['FillValue']
            except:
                logger.debug('Cannot get attribute FillValue for variable %s from url %s', var, self.url)
            return None
        else:
            return fv

    def getFeatureType(self):
        '''
        Return string of featureType from table at http://cf-pcmdi.llnl.gov/documents/cf-conventions/1.6/ch09.html.
        Accomodate previous concepts of this attribute and convert to the new discrete sampling geometry conventions in CF-1.6.
        Possible return values: 'trajectory', 'timeseries', 'timeseriesprofile', lowercase versions.
        '''
        conventions = ''
        try:
            nc_global_keys = self.ds.attributes['NC_GLOBAL']
        except KeyError:
            logger.warn('Dataset does not have an NC_GLOBAL attribute! Setting featureType to "trajectory" assuming that this is an old Tethys file')
            return 'trajectory'

        if 'Conventions' in nc_global_keys:
            conventions = self.ds.attributes['NC_GLOBAL']['Conventions'].lower()
        elif 'Conventions' in nc_global_keys:
            conventions = self.ds.attributes['NC_GLOBAL']['Convention'].lower()
        elif 'conventions' in nc_global_keys:
            conventions = self.ds.attributes['NC_GLOBAL']['conventions'].lower()
        else:
            conventions = ''

        if conventions == 'cf-1.6':
            featureType = self.ds.attributes['NC_GLOBAL']['featureType']
        else:
            # Accept earlier versions of the concept of this attribute that may be in legacy data sets
            if 'cdm_data_type' in nc_global_keys:
                featureType = self.ds.attributes['NC_GLOBAL']['cdm_data_type']
            elif 'thredds_data_type' in nc_global_keys:
                featureType = self.ds.attributes['NC_GLOBAL']['thredds_data_type'] 
            elif 'CF%3afeatureType' in nc_global_keys:
                featureType = self.ds.attributes['NC_GLOBAL']['CF%3afeatureType']
            elif 'CF_featureType' in nc_global_keys:
                featureType = self.ds.attributes['NC_GLOBAL']['CF_featureType']
            else:
                featureType = ''

        if featureType.lower() == 'station':
            # Used in elvis' TDS mooring data aggregation, it's really 'timeSeriesProfile'
            featureType = 'timeSeriesProfile'

        if featureType.lower() == 'Trajectory':
            featureType = 'trajectory'

        # Put the CF-1.6 proper featureType into NC_GLOBAL so that addResources will put it into the database
        self.ds.attributes['NC_GLOBAL']['featureType'] = featureType

        return featureType.lower()

    def getAuxCoordinates(self, variable):
        '''
        Return a dictionary of a variable's auxilary coordinates mapped to the standard_names of 'time', 'latitude',
        'longitude', and 'depth'.  Accomodate previous ways of associating these variables and convert to the new 
        CF-1.6 conventions as outlined in Chapter 5 of the document.  If an auxCoord dictionary is passed to the
        Loader then that dictionary will be returned.  This is handy for datasets that are not yet compliant.  
        Requirements for compliance: variables have a coordinates attribute listing the 4 geospatial/temporal 
        coordinates, the coordinate variables have standard_names of 'time', 'latitude', 'longitude', 'depth'.
        Example return value: {'time': 'esecs', 'depth': 'DEPTH', 'latitude': 'lat', 'longitude': 'lon'}
        '''
        if self.auxCoords:
            if variable in self.auxCoords:
                # Simply return self.auxCoords if specified in the constructor
                logger.debug('Returning auxCoords for variable %s that were specified in the constructor: %s', variable, self.auxCoords[variable])
                return self.auxCoords[variable]
            else:
                raise ParameterNotFound('auxCoords is specified, but variable requested (%s) is not in %s' % (variable, self.auxCoords))

        # Scan variable standard_name attributes for ('time', 'latitude', 'longitude', 'depth') standard_name's
        # There is no check here for multiple multiple time, latitude, longitude, or depth coordinates.  Should
        # CF say something about multiple coordinate axes in a file, i.e. should there just be one?
        coordSN = {}
        snCoord = {}
        for k in self.ds.keys():
            if 'standard_name' in self.ds[k].attributes:
                if self.ds[k].attributes['standard_name'] in ('time', 'latitude', 'longitude', 'depth'):
                    coordSN[k] = self.ds[k].attributes['standard_name']
                    snCoord[self.ds[k].attributes['standard_name']] = k

        # Match items in coordinate attribute, via coordinate standard_name to coordinate name
        if variable not in self.ds:
            raise ParameterNotFound('Variable %s is not in dataset %s' % (variable, self.url))

        coordDict = {}
        if 'coordinates' in self.ds[variable].attributes:
            for coord in self.ds[variable].attributes['coordinates'].split():
                logger.debug(coord)
                try:
                    logger.debug(snCoord)
                    ##coordDict[coord] = coordSN[coord]
                    coordDict[coordSN[coord]] = coord
                except KeyError, e:
                    raise AuxCoordMissingStandardName(e)
        else:
            logger.warn('Variable %s is missing coordinates attribute', variable)
            raise VariableMissingCoordinatesAttribute('%s: %s missing coordinates attribute' % (self.url, variable,))

        # Check for all 4 coordinates needed for spatial-temporal location - if any are missing raise exception with suggestion
        reqCoords = set(('time', 'latitude', 'longitude', 'depth'))
        logger.debug('coordDict = %s', coordDict)
        if set(coordDict.keys()) != reqCoords:
            logger.warn('Required coordinate(s) %s missing.  Consider overriding by setting an auxCoords dictionary in your Loader.', list(reqCoords - set(coordDict.keys())))
            raise VariableMissingCoordinatesAttribute('%s: %s missing coordinates attribute' % (self.url, variable,))

        logger.debug('coordDict = %s', coordDict)

        return coordDict

    def getNominalLocation(self):
        '''
        For timeSeries and timeSeriesProfile data return nominal location as a tuple of (depth, latitude, longitude) as
        expressed in the coordinate variables of the mooring or station. For timeSeries features depth will be a scalar, 
        for timeSeriesProfile depth will be an array of depths.
        '''
        depths = {}
        lats = {}
        lons = {}
        for v in self.include_names:
            logger.debug('Calling self.getAuxCoordinates() for v = %s', v)
            try:
                ac = self.getAuxCoordinates(v)
            except ParameterNotFound, e:
                logger.warn('Skipping include_name = %s: %s', v, e)
                continue
     
            # depth may be single-valued or an array 
            if self.getFeatureType() == 'timeseries': 
                logger.debug('Initializing depths list for timeseries, ac = %s', ac)
                depths[v] = self.ds[v][ac['depth']][:][0]
            elif self.getFeatureType() == 'timeseriesprofile':
                logger.debug('Initializing depths list for timeseriesprofile, ac = %s', ac)
                depths[v] = self.ds[v][ac['depth']][:]

            # latitude and longitude are always single-valued
            lats[v] = self.ds[v][ac['latitude']][:][0]
            lons[v] = self.ds[v][ac['longitude']][:][0]

        # All variables must have the same nominal location 
        if len(set(lats.values())) != 1 or len(set(lons.values())) != 1:
            raise Exception('Invalid file coordinates structure.  All variables must have identical nominal lat & lon, lats = %s, lons = %s', lats, lons)
        else:
            lat = lats.values()[0]
            lon = lons.values()[0]

        if len(set(lats.values())) != 1 or len(set(lons.values())) != 1:
            raise Exception('Invalid file coordinates structure.  All variables must have identical nominal latitude and longitude. lats = %s, lons = %s' % (lats, lons))

        return depths, lats, lons

    def getTimeBegEndIndices(self, timeAxis):
        '''
        Return begining and ending indices for the corresponding time axis indices
        '''
        timeAxisUnits =  timeAxis.units.lower()
        timeAxisUnits = timeAxisUnits.replace('utc', 'UTC')        # coards requires UTC to be upper case 
        if timeAxis.units == 'seconds since 1970-01-01T00:00:00Z':
            timeAxisUnits = 'seconds since 1970-01-01 00:00:00'    # coards doesn't like ISO format
        if self.startDatetime: 
            logger.debug('self.startDatetime, timeAxis.units = %s, %s', self.startDatetime, timeAxis.units)
            s = to_udunits(self.startDatetime, timeAxisUnits)
            logger.debug("For startDatetime = %s, the udnits value is %f", self.startDatetime, s)

        if self.endDatetime:
            'endDatetime may be None, in which case just read until the end'
            e = to_udunits(self.endDatetime, timeAxisUnits)
            logger.debug("For endDatetime = %s, the udnits value is %f", self.endDatetime, e)
        else:
            e = timeAxis[-1]
            logger.info("endDatetime not given, using the last value of timeAxis = %f", e)

        tf = (s <= timeAxis) & (timeAxis <= e)
        logger.debug('tf = %s', tf)
        tIndx = numpy.nonzero(tf == True)[0]
        if tIndx.size == 0:
            raise NoValidData('No data from %s for time values between %s and %s.  Skipping.' % (self.url, s, e))

        # For python slicing add 1 to the end index
        logger.debug('tIndx = %s', tIndx)
        try:
            indices = (tIndx[0], tIndx[-1] + 1)
        except IndexError:
            raise NoValidData('Could not get first and last indexes from tIndex = %s. Skipping.' % (tIndx))
        logger.info('Start and end indices are: %s', indices)

        return indices

    def getTotalRecords(self):
        '''
        For the url count all the records that are to be loaded from all the include_names and return it.
        '''
        count = 0
        numDerived = 0
        trajSingleParameterCount = 0
        for name in self.include_names:
            try:
                if self.getFeatureType() == 'trajectory':
                    trajSingleParameterCount = np.prod(self.ds[name].shape)
                count += (np.prod(self.ds[name].shape) / self.stride)
            except KeyError as e:
                if self.getFeatureType() == 'trajectory':
                    # Assume that it's a derived variable and add same count as 
                    logger.warn("%s: Assuming it's a derived parameter", e)
                    numDerived += 1
                    
        logger.debug('Adding %d derived parameters of length %d to the count', numDerived, trajSingleParameterCount / self.stride)
        if trajSingleParameterCount:
            count += (numDerived * trajSingleParameterCount / self.stride)

        return count 

    def _genTimeSeriesGridType(self):
        '''
        Generator of TimeSeriesProfile (tzyx where z is multi-valued) and TimeSeries (tzyx where z is single-valued) data.
        Using terminology from CF-1.6 assume data is from a discrete sampling geometry type of timeSeriesProfile or timeSeries.
        Provides a uniform dictionary that contains attributes and their associated values without the need
        to individualize code for each data source.
        '''
        data = {} 
        times = {}
        depths = {}
        latitudes = {}
        longitudes = {}
        timeUnits = {}

        # Read the data from the OPeNDAP url into arrays keyed on parameter name - these arrays may take a bit of memory 
        # The reads here take advantage of OPeNDAP access mechanisms to effeciently transfer data across the network
        for pname in self.include_names:
            if pname not in self.ds:
                continue    # Quietly skip over parameters not in ds: allows combination of variables and files in same loader
            # Peek at the shape and pull apart the data from its grid coordinates 
            logger.info('Reading data from %s: %s', self.url, pname)
            if len(self.ds[pname].shape) == 4 and type(self.ds[pname]) is pydap.model.GridType:
                # On tzyx grid - default for all OS formatted station data COARDS coordinate ordering conventions
                # E.g. for http://elvis.shore.mbari.org/thredds/dodsC/agg/OS_MBARI-M1_R_TS, shape = (74040, 11, 1, 1) 
                #       or http://elvis.shore.mbari.org/thredds/dodsC/agg/OS_MBARI-M1_R_TS, shape = (74850, 1, 1, 1)
                tIndx = self.getTimeBegEndIndices(self.ds[self.ds[pname].keys()[1]])
                try:
                    # Subselect along the time axis, get all z values
                    logger.info("Using constraints: ds['%s']['%s'][%d:%d:%d,:,0,0]", pname, pname, tIndx[0], tIndx[-1], self.stride)
                    v = self.ds[pname][pname][tIndx[0]:tIndx[-1]:self.stride,:,0,0]
                except ValueError, err:
                    logger.error('''\nGot error '%s' reading data from URL: %s.", err, self.url
                    If it is: 'string size must be a multiple of element size' and the URL is a TDS aggregation
                    then the cache files must be removed and the tomcat hosting TDS restarted.''')
                    sys.exit(1)
                except pydap.exceptions.ServerError as e:
                    if self.stride > 1:
                        logger.warn('%s and stride > 1.  Skipping dataset %s', e, self.url)
                        continue
                    else:
                        logger.exception('%s', e)
                        sys.exit(-1)
    
                # The STOQS datavalue 
                data[pname] = iter(v)      # Iterator on time axis delivering all z values in an array with .next()

                # CF (nee COARDS) has tzyx coordinate ordering
                times[pname] = self.ds[self.ds[pname].keys()[1]][tIndx[0]:tIndx[-1]:self.stride]
                depths[pname] = self.ds[self.ds[pname].keys()[2]][:]                # TODO lookup more precise depth from conversion from pressure
                latitudes[pname] = float(self.ds[self.ds[pname].keys()[3]][0])      # TODO lookup more precise gps lat
                longitudes[pname] = float(self.ds[self.ds[pname].keys()[4]][0])     # TODO lookup more precise gps lon
                timeUnits[pname] = self.ds[self.ds[pname].keys()[1]].units.lower()
                timeUnits[pname] = timeUnits[pname].replace('utc', 'UTC')           # coards requires UTC in uppercase
                if self.ds[self.ds[pname].keys()[1]].units == 'seconds since 1970-01-01T00:00:00Z':
                    timeUnits[pname] = 'seconds since 1970-01-01 00:00:00'          # coards doesn't like ISO format

                nomDepths, nomLats, nomLons = self.getNominalLocation()
            else:
                logger.warn('Variable %s is not of type pydap.model.GridType with a shape length of 4.  It has a shape length of %d.', pname, len(self.ds[pname].shape))

        # Deliver the data harmonized as rows as an iterator so that they are fed as needed to the database
        for pname in data.keys():
            logger.info('Delivering rows of data for %s', pname)
            l = 0
            for depthArray in data[pname]:
                k = 0
                logger.debug('depthArray = %s', depthArray)
                logger.debug('nomDepths = %s', nomDepths)
                ##raw_input('PAUSED')
                values = {}
                for dv in depthArray:
                    values[pname] = float(dv)
                    values['time'] = times[pname][l]
                    values['depth'] = depths[pname][k]
                    values['latitude'] = latitudes[pname]
                    values['longitude'] = longitudes[pname]
                    values['timeUnits'] = timeUnits[pname]
                    try:
                        values['nomDepth'] = nomDepths[pname][k]
                    except IndexError:
                        values['nomDepth'] = nomDepths[pname]
                    values['nomLat'] = nomLats[pname]
                    values['nomLon'] = nomLons[pname]
                    yield values
                    k = k + 1

                l = l + 1

    def _genTrajectory(self):
        '''
        Generator of trajectory data. The data values are a function of time and the coordinates attribute 
        identifies the depth, latitude, and longitude from where the measurement was made.
        Using terminology from CF-1.6 assume data is from a discrete geometry type of trajectory.
        Provides a uniform dictionary that contains attributes and their associated values without the need
        to individualize code for each data source.
        '''
        ac = {}
        data = {} 
        times = {}
        depths = {}
        latitudes = {}
        longitudes = {}
        timeUnits = {}

        # Read the data from the OPeNDAP url into arrays keyed on parameter name - these arrays may take a bit of memory 
        # The reads here take advantage of OPeNDAP access mechanisms to effeciently transfer data across the network
        for pname in self.include_names:
            if pname not in self.ds.keys():
                logger.warn('include_name %s not in dataset %s', pname, self.url)
                continue
            # Peek at the shape and pull apart the data from its grid coordinates 
            # Only single trajectories are allowed
            logger.info('Reading data from %s: %s', self.url, pname)
            if len(self.ds[pname].shape) == 1 and type(self.ds[pname]) is pydap.model.BaseType:
                # Legacy Dorado data need to be processed as BaseType; Example data:
                #   dsdorado = open_url('http://odss.mbari.org/thredds/dodsC/CANON_september2012/dorado/Dorado389_2012_256_00_256_00_decim.nc')
                #   dsdorado['temperature'].shape = (12288,)
                ac[pname] = self.getAuxCoordinates(pname)
                try:
                    logger.debug("ac[pname]['time'] = %s", ac[pname]['time'])
                    tIndx = self.getTimeBegEndIndices(self.ds[ac[pname]['time']])
                except NoValidData, e:
                    logger.warn('Skipping this parameter. %s' % e)
                    continue
                try:
                    # Subselect along the time axis
                    logger.info("Using constraints: ds['%s'][%d:%d:%d]", pname, tIndx[0], tIndx[-1], self.stride)
                    v = self.ds[pname][tIndx[0]:tIndx[-1]:self.stride]
                except ValueError, err:
                    logger.error('''\nGot error '%s' reading data from URL: %s.", err, self.url
                    If it is: 'string size must be a multiple of element size' and the URL is a TDS aggregation
                    then the cache files must be removed and the tomcat hosting TDS restarted.''', err, self.url)
                    sys.exit(1)
                except pydap.exceptions.ServerError as e:
                    logger.exception('%s', e)
                    sys.exit(-1)
                    continue
    
                # The STOQS datavalue 
                data[pname] = iter(v)      # Iterator on time axis delivering all values in an array with .next()

                # Peek at coordinate attribute to get depth, latitude, longitude values from the other BaseTypes
                logger.info('ac = %s', ac)

                times[pname] = self.ds[ac[pname]['time']][tIndx[0]:tIndx[-1]:self.stride]
                try:
                    depths[pname] = self.ds[ac[pname]['depth']][tIndx[0]:tIndx[-1]:self.stride]
                except KeyError:
                    # Allow for variables with no depth coordinate to be loaded at the depth specified in auxCoords
                    if isinstance(ac[pname]['depth'], float):
                        depths[pname] =  ac[pname]['depth'] * numpy.ones(len(times[pname]))

                latitudes[pname] = self.ds[ac[pname]['latitude']][tIndx[0]:tIndx[-1]:self.stride]
                longitudes[pname] = self.ds[ac[pname]['longitude']][tIndx[0]:tIndx[-1]:self.stride]
                timeUnits[pname] = self.ds[ac[pname]['time']].units.lower()
                timeUnits[pname] = timeUnits[pname].replace('utc', 'UTC')           # coards requires UTC in uppercase
                if self.ds[ac[pname]['time']].units == 'seconds since 1970-01-01T00:00:00Z':
                    timeUnits[pname] = 'seconds since 1970-01-01 00:00:00'          # coards doesn't like ISO format

            elif len(self.ds[pname].shape) == 1 and type(self.ds[pname]) is pydap.model.GridType:
                # LRAUV data need to be processed as GridType
                ac[pname] = self.getAuxCoordinates(pname)
                tIndx = self.getTimeBegEndIndices(self.ds[ac[pname]['time']])
                try:
                    # Subselect along the time axis
                    logger.info("Using constraints: ds['%s']['%s'][%d:%d:%d]", pname, pname, tIndx[0], tIndx[-1], self.stride)
                    v = self.ds[pname][pname][tIndx[0]:tIndx[-1]:self.stride]
                except ValueError, err:
                    logger.error('''\nGot error '%s' reading data from URL: %s.", err, self.url
                    If it is: 'string size must be a multiple of element size' and the URL is a TDS aggregation
                    then the cache files must be removed and the tomcat hosting TDS restarted.''')
                    sys.exit(1)
                except pydap.exceptions.ServerError as e:
                    logger.error('%s', e)
                    continue
    
                # The STOQS datavalue 
                data[pname] = iter(v)      # Iterator on time axis delivering all values in an array with .next()

                # Peek at coordinate attribute to get depth, latitude, longitude values from the other BaseTypes
                logger.info('ac = %s', ac)

                times[pname] = self.ds[ac[pname]['time']][tIndx[0]:tIndx[-1]:self.stride]
                depths[pname] = self.ds[ac[pname]['depth']][ac[pname]['depth']][tIndx[0]:tIndx[-1]:self.stride]
                latitudes[pname] = self.ds[ac[pname]['latitude']][ac[pname]['latitude']][tIndx[0]:tIndx[-1]:self.stride]
                longitudes[pname] = self.ds[ac[pname]['longitude']][ac[pname]['longitude']][tIndx[0]:tIndx[-1]:self.stride]
                timeUnits[pname] = self.ds[ac[pname]['time']].units.lower()

            else:
                logger.warn('Variable %s is not of type pydap.model.GridType with a shape length of 1.  It is type %s with shape length = %d.', 
                            pname, type(self.ds[pname]), len(self.ds[pname].shape))

        # Deliver the data harmonized as rows as an iterator so that they are fed as needed to the database
        for pname in data.keys():
            logger.debug('Delivering rows of data for %s', pname)
            l = 0
            values = {}
            for dv in data[pname]:
                values[pname] = float(dv)
                values['time'] = times[pname][l]
                values['depth'] = depths[pname][l]
                values['latitude'] = latitudes[pname][l]
                values['longitude'] = longitudes[pname][l]
                values['timeUnits'] = timeUnits[pname]
                yield values
                l = l + 1

    def _insertRow(self, parmCount, parameterCount, measurement, row):
        '''
        Insert a row of MeasuredParameters as returned from our data generators.
        Perform inside an inner method to commit only on success as some saves may result in 
        database integrity errors and we need to recover from them gracefully.
        '''
        @transaction.commit_on_success(using=self.dbAlias)
        def _innerInsertRow(self, parmCount, parameterCount, measurement, row):

            for key, value in row.iteritems():
                try:
                    logger.debug('Checking for %s in self.include_names', key)
                    if len(self.include_names) and key not in self.include_names:
                        continue
                    elif key in self.ignored_names:
                        continue

                    # If the data have a Z dependence (e.g. mooring tstring/adcp) then value will be an array.
                    logger.debug("value = %s ", value)
                    
                    if value > 1e34 and value != self.get_FillValue(key):
                        # Workaround for IOOS glider data
                        if abs(value - self.get_FillValue(key)) < 1e24:
                            # Equal to 10 digits
                            continue
                        elif abs(value - self.getmissing_value(key)) < 1e24:
                            # Equal to 10 digits
                            continue
                        else:
                            logger.error('Invalid data value: > 1e34, but not close to _FillValue or missing_value. Entering debugger...')
                            import pdb; pdb.set_trace()

                    if value == self.getmissing_value(key) or value == self.get_FillValue(key) or value == 'null' or numpy.isnan(value): # absence of a value
                        continue
                    try:
                        if math.isnan(value): # not a number for a math type
                            continue
                    except Exception, e: 
                        logger.debug('%s', e)
                        pass

                    logger.debug("measurement._state.db = %s", measurement._state.db)
                    logger.debug("key = %s", key)
                    logger.debug("parameter._state.db = %s", self.getParameterByName(key)._state.db)
                    parameter = self.getParameterByName(key)
                    mp = m.MeasuredParameter(measurement=measurement, parameter=parameter, datavalue=value)
                    logger.debug('Saving parameter_id %s at measurement_id = %s', parameter.id, measurement.id)
                    try:
                        mp.save(using=self.dbAlias)
                    except IntegrityError as e:
                        logger.warn('%s: Skipping this record.', e)
                    except DatabaseError as e:
                        logger.warn('%s: Skipping this record.', e)
                    else:
                        self.loaded += 1
                        logger.debug("Inserted value (id=%(id)s) for %(key)s = %(value)s", {'key': key, 'value': value, 'id': mp.pk})
                        parmCount[key] += 1
                        if parameterCount.has_key(self.getParameterByName(key)):
                            parameterCount[self.getParameterByName(key)] += 1
                        else:
                            parameterCount[self.getParameterByName(key)] = 0

                except ParameterNotFound:
                    print "Unable to locate parameter for %s, skipping" % (key,)

                if self.loaded:
                    if (self.loaded % 500) == 0:
                        logger.info("%s: %d of about %d records loaded.", self.url.split('/')[-1], self.loaded, self.totalRecords)

            # End for key, value

        return _innerInsertRow(self, parmCount, parameterCount, measurement, row)


    def process_data(self): 
      '''
      Wrapper so as to apply self.dbAlias in the decorator
      '''
      def innerProcess_data(self):
        '''
        Iterate over the data source and load the data in by creating new objects
        for each measurement.
        
        Note that due to the use of large-precision numerics, we'll convert all numbers to
        strings prior to performing the import.  Django uses the Decimal type (arbitrary precision
        numeric type), so we won't lose any precision.

        Return the number of MeasuredParameters loaded.
        '''

        self.initDB()

        self.loaded = 0
        parmCount = {}
        parameterCount = {}
        mindepth = 8000.0
        maxdepth = -8000.0
        for key in self.include_names:
            parmCount[key] = 0

        self.totalRecords = self.getTotalRecords()

        logger.info('self.getFeatureType() = %s', self.getFeatureType())
        if self.getFeatureType() == 'timeseriesprofile':
            data_generator = self._genTimeSeriesGridType()
            featureType = 'timeseriesprofile'
        elif self.getFeatureType() == 'timeseries':
            data_generator = self._genTimeSeriesGridType()
            featureType = 'timeseries'
        elif self.getFeatureType() == 'trajectory':
            data_generator = self._genTrajectory()
            featureType = 'trajectory'

        if not featureType:
            raise Exception("Global attribute 'featureType' is not one of 'trajectory', 'timeSeries', or 'timeSeriesProfile' - see http://cf-pcmdi.llnl.gov/documents/cf-conventions/1.6/ch09.html")

        for row in data_generator:
            logger.debug(row)
            try:
                row = self.preProcessParams(row)
                logger.debug("After preProcessParams():")
                logger.debug(row)
            except SkipRecord:
                logger.debug("Got SkipRecord Exception from self.preProcessParams().  Skipping")
                continue
            except Exception, e:
                logger.exception(e)
                sys.exit(-1)
            else:
                params = {} 
                try:
                    if featureType == 'timeseriesprofile' or featureType == 'timeseries':
                        longitude, latitude, time, depth, nomLon, nomLat, nomDepth = (row.pop('longitude'), row.pop('latitude'),
                                                            from_udunits(row.pop('time'), row.pop('timeUnits')),
                                                            row.pop('depth'), row.pop('nomLon'), row.pop('nomLat'),row.pop('nomDepth'))
                        measurement = self.createMeasurement(featureType, time=time, depth=depth, lat=latitude, long=longitude,
                                                            nomDepth=nomDepth, nomLat=nomLat, nomLong=nomLon)
                    else:
                        longitude, latitude, time, depth = (row.pop('longitude'), row.pop('latitude'),
                                                            from_udunits(row.pop('time'), row.pop('timeUnits')),
                                                            row.pop('depth'))

                        measurement = self.createMeasurement(featureType, time=time, depth=depth, lat=latitude, long=longitude)
                except ValueError:
                    logger.info('Bad time value')
                    continue
                except SkipRecord, e:
                    logger.debug("Skipping record: %s", e)
                    continue
                except Exception, e:
                    logger.exception(e)
                    sys.exit(-1)
                else:
                    logger.debug("longitude = %s, latitude = %s, time = %s, depth = %s", longitude, latitude, time, depth)
                    if depth < mindepth:
                        mindepth = depth
                    if depth > maxdepth:
                        maxdepth = depth

            self._insertRow(parmCount, parameterCount, measurement, row)


        # End for row

        #
        # Query database to a path for trajectory or stationPoint for timeSeriesProfile and timeSeries
        #
        path = None
        stationPoint = None
        linestringPoints = m.Measurement.objects.using(self.dbAlias).filter(instantpoint__activity=self.activity
                                                       ).order_by('instantpoint__timevalue').values_list('geom')
        try:
            path = LineString([p[0] for p in linestringPoints]).simplify(tolerance=.001)
        except TypeError, e:
            logger.warn("%s\nSetting path to None", e)
        except Exception as e:
            logger.error('%s', e)    # Likely "GEOS_ERROR: IllegalArgumentException: point array must contain 0 or >1 elements"
        else:
            if len(path) == 2:
                logger.info("Length of path = 2: path = %s", path)
                if path[0][0] == path[1][0] and path[0][1] == path[1][1]:
                    logger.info("And the 2 points are identical. Saving the first point of this path as a point as the featureType is also %s.", featureType)
                    stationPoint = Point(path[0][0], path[0][1])
                    path = None

        # Add additional Parameters for all appropriate Measurements
        logger.info("Adding SigmaT and Spiciness to the Measurements...")
        self.addSigmaTandSpice(parameterCount, self.activity)
        if self.grdTerrain:
            logger.info("Adding altitude to the Measurements...")
            self.addAltitude(parameterCount, self.activity)

        # Update the Activity with information we now have following the load
        newComment = "%d MeasuredParameters loaded: %s. Loaded on %sZ" % (self.loaded, ' '.join(self.varsLoaded), datetime.utcnow())
        logger.debug("Updating its comment with newComment = %s", newComment)

        num_updated = m.Activity.objects.using(self.dbAlias).filter(id=self.activity.id).update(
                        comment = newComment,
                        maptrack = path,
                        mappoint = stationPoint,
                        mindepth = mindepth,
                        maxdepth = maxdepth,
                        num_measuredparameters = self.loaded,
                        loaded_date = datetime.utcnow())
        logger.debug("%d activitie(s) updated with new attributes.", num_updated)

        #
        # Add resources after loading data to capture additional metadata that may be added
        #
        try:
            self.addResources() 
        except IntegrityError, e:
            logger.error('Failed to properly addResources: %s', e)

        # 
        # Update the stats and store simple line values
        #
        self.updateActivityParameterStats(parameterCount)
        self.updateCampaignStartEnd()
        self.assignParameterGroup(parameterCount, groupName=MEASUREDINSITU)
        if self.getFeatureType().lower() == 'trajectory':
            self.insertSimpleDepthTimeSeries()
            self.saveBottomDepth()
            self.insertSimpleBottomDepthTimeSeries()
        elif self.getFeatureType().lower() == 'timeseries' or self.getFeatureType().lower() == 'timeseriesprofile':
            self.insertSimpleDepthTimeSeriesByNominalDepth()
        logger.info("Data load complete, %d records loaded.", self.loaded)


        return self.loaded, path, parmCount, mindepth, maxdepth

      return innerProcess_data(self)


class Trajectory_Loader(Base_Loader):
    '''
    Generic loader for trajectory data.  May be subclassed if special data or metadata processing 
    is needed for a particular kind of trajectory data.
    '''
    include_names = ['temperature', 'conductivity']

    def preProcessParams(self, row):
        '''
        Compute on-the-fly any additional parameters for loading into the database
        '''
        # Compute salinity if it's not in the record and we have temperature, conductivity, and pressure
        ##if row.has_key('temperature') and row.has_key('pressure') and row.has_key('latitude'):
        ##  conductivity_ratio = row['conductivity'] / 
        ##  row['salinity'] = sw.salt(conductivity_ratio, sw.T90conv(row['temperature']), row['pressure'])

        # TODO: Compute sigma-t if we have standard_names of sea_water_salinity, sea_water_temperature and sea_water_pressure

        # TODO: Lookup bottom depth here and create new bottom depth and altitude parameters...

        return super(Trajectory_Loader, self).preProcessParams(row)


class Dorado_Loader(Trajectory_Loader):
    '''
    MBARI Dorado data as read from the production archive.  This class includes overridded methods
    to load quick-look plot and other Resources into the STOQS database.
    '''
    chl = pydap.model.BaseType()
    chl.attributes = {  'standard_name':    'mass_concentration_of_chlorophyll_in_sea_water',
                        'long_name':        'Chlorophyll',
                        'units':            'ug/l',
                        'name':             'mass_concentration_of_chlorophyll_in_sea_water',
                     }
    dens = pydap.model.BaseType()
    dens.attributes = { 'standard_name':    'sea_water_sigma_t',
                        'long_name':        'Sigma-T',
                        'units':            'kg m-3',
                        'name':             'sea_water_sigma_t',
                      }
    parmDict = {    'mass_concentration_of_chlorophyll_in_sea_water': chl,
                    'sea_water_sigma_t': dens
               }
    include_names = [   'temperature', 'oxygen', 'nitrate', 'bbp420', 'bbp700', 
                        'fl700_uncorr', 'salinity', 'biolume',
                        'mass_concentration_of_chlorophyll_in_sea_water',
                        'sea_water_sigma_t' ]

    def initDB(self):
        '''
        Make sure our added Parameters of mass_concentration_of_chlorophyll_in_sea_water and sea_water_sigma_t are included
        '''
        self.addParameters(self.parmDict)
        logger.debug('Appending to self.varsLoaded = %s', self.varsLoaded)
        for k in self.parmDict.keys():
            self.varsLoaded.append(k)       # Make sure to add the derived parameters to the list that gets put in the comment

        return super(Dorado_Loader, self).initDB()

    def preProcessParams(self, row):
        '''
        Compute on-the-fly any additional Dorado parameters for loading into the database
        '''
        # Magic formula for October 2010 CANON "experiment"
        if row.has_key('fl700_uncorr'):
            row['mass_concentration_of_chlorophyll_in_sea_water'] = 3.4431e+03 * row['fl700_uncorr']

        # Compute sigma-t
        if row.has_key('salinity') and row.has_key('temperature') and row.has_key('depth') and row.has_key('latitude'):
            row['sea_water_sigma_t'] = sw.pden(row['salinity'], row['temperature'], sw.pres(row['depth'], row['latitude'])) - 1000.0

        return super(Dorado_Loader, self).preProcessParams(row)

    def addResources(self):
        '''
        In addition to the NC_GLOBAL attributes that are added in the base class also add the quick-look plots that are on the dods server.
        '''
        baseUrl = 'http://dods.mbari.org/data/auvctd/surveys'
        survey = self.url.split('/')[-1].split('.nc')[0].split('_decim')[0] # Works for both .nc and _decim.nc files
        yyyy = int(survey.split('_')[1])
        # Quick-look plots
        logger.debug("Getting or Creating ResourceType quick_look...")
        (resourceType, created) = m.ResourceType.objects.db_manager(self.dbAlias).get_or_create(
                        name = 'quick_look', description='Quick Look plot of data from this AUV survey')
        for ql in ['2column', 'biolume', 'hist_stats', 'lopc', 'nav_adjust', 'prof_stats']:
            url = '%s/%4d/images/%s_%s.png' % (baseUrl, yyyy, survey, ql)
            logger.debug("Getting or Creating Resource with name = %s, url = %s", ql, url )
            (resource, created) = m.Resource.objects.db_manager(self.dbAlias).get_or_create(
                        name=ql, uristring=url, resourcetype=resourceType)
            (ar, created) = m.ActivityResource.objects.db_manager(self.dbAlias).get_or_create(
                        activity=self.activity,
                        resource=resource)

        # kml, odv, mat
        (kmlResourceType, created) = m.ResourceType.objects.db_manager(self.dbAlias).get_or_create(
                        name = 'kml', description='Keyhole Markup Language file of data from this AUV survey')
        (odvResourceType, created) = m.ResourceType.objects.db_manager(self.dbAlias).get_or_create(
                        name = 'odv', description='Ocean Data View spreadsheet text file')
        (matResourceType, created) = m.ResourceType.objects.db_manager(self.dbAlias).get_or_create(
                        name = 'mat', description='Matlab data file')
        for res in ['kml', 'odv', 'odvGulper', 'mat', 'mat_gridded']:
            if res == 'kml':
                url = '%s/%4d/kml/%s.kml' % (baseUrl, yyyy, survey)
                rt = kmlResourceType
            elif res == 'odv':
                url = '%s/%4d/odv/%s.txt' % (baseUrl, yyyy, survey)
                rt = odvResourceType
            elif res == 'odvGulper':
                url = '%s/%4d/odv/%s_Gulper.txt' % (baseUrl, yyyy, survey)
                rt = odvResourceType
            elif res == 'mat':
                url = '%s/%4d/mat/%s.mat' % (baseUrl, yyyy, survey)
                rt = matResourceType
            elif res == 'mat_gridded':
                url = '%s/%4d/mat/%s_gridded.mat' % (baseUrl, yyyy, survey)
                rt = matResourceType
            else:
                logger.warn('No handler for res = %s', res)

            logger.debug("Getting or Creating Resource with name = %s, url = %s", res, url )
            (resource, created) = m.Resource.objects.db_manager(self.dbAlias).get_or_create(
                        name=res, uristring=url, resourcetype=rt)
            (ar, created) = m.ActivityResource.objects.db_manager(self.dbAlias).get_or_create(
                        activity=self.activity, resource=resource)

        return super(Dorado_Loader, self).addResources()


class Lrauv_Loader(Trajectory_Loader):
    '''
    MBARI Long Range AUV data loader.
    '''
    dens = pydap.model.BaseType()
    dens.attributes = { 'standard_name':    'sea_water_sigma_t',
                        'long_name':        'Sigma-T',
                        'units':            'kg m-3',
                        'name':             'sea_water_sigma_t'
                      }
    parmDict = {'sea_water_sigma_t': dens}
    include_names = [   'mass_concentration_of_oxygen_in_sea_water',
                        'mole_concentration_of_nitrate_in_sea_water',
                        'mass_concentration_of_chlorophyll_in_sea_water',
                        'sea_water_salinity',
                        'sea_water_temperature',
                        'sea_water_sigma_t',
                    ]

    def initDB(self):
        self.addParameters(self.parmDict)
        for k in self.parmDict.keys():
            self.varsLoaded.append(k)       # Make sure to add the derived parameters to the list that gets put in the comment

        return super(Lrauv_Loader, self).initDB()

    def preProcessParams(self, row):
        '''
        Special fixups for 'shore' synchronized data
        '''
        if self.url.find('shore') == -1 and self.url.find('Tethys') == -1 and self.url.find('Daphne') == -1 and self.url.find('hotspot'):
            # Full-resolution data (whose name does not contain 'shore', 'Tethys', 'Daphne', 'hotspot') are in radians
            if row.has_key('latitude'):
                row['latitude'] = row['latitude'] * 180.0 / numpy.pi
            if row.has_key('longitude'):
                row['longitude'] = row['longitude'] * 180.0 / numpy.pi
            # Can't read CTD_NeilBrown.sea_water_temperature because of the '.'.  Use 'sea_water_temperature', but convert to C and assign units
            if row.has_key('sea_water_temperature'):
                row['sea_water_temperature'] = row['sea_water_temperature'] - 272.15
                self.ds['sea_water_temperature'].units = 'degC'

        return super(Lrauv_Loader, self).preProcessParams(row)


class Glider_Loader(Trajectory_Loader):
    '''
    CenCOOS Line 66 Spray glider data loader
    '''
    include_names=['TEMP', 'PSAL', 'OPBS', 'FLU2']

    def preProcessParams(self, row):
        '''
        Placeholder for any special preprocessing for Glider data
        '''
        return super(Glider_Loader,self).preProcessParams(row)


class TimeSeries_Loader(Base_Loader):
    '''
    Generic loader for station (non-trajectory) data.  Expects CF-1.6 timeSeries discrete sampling geometry featureType.
    '''
    # Subclasses or calling function must specify include_names
    include_names=[]

    def preProcessParams(self, row):
        '''
        Placeholder for any special preprocessing, for example adding sigma-t or other derived parameters
        '''
        return super(TimeSeries_Loader,self).preProcessParams(row)


class Mooring_Loader(TimeSeries_Loader):
    '''
    OceanSITES formatted Mooring data loader.  Expects CF-1.6 timeSeriesProfile discrete sampling geometry type.
    '''
    include_names=['Temperature', 'Salinity', 'TEMP', 'PSAL', 'ATMP', 'AIRT', 'WDIR', 'WSDP']

    def preProcessParams(self, row):
        '''
        Placeholder for any special preprocessing for Mooring data
        '''
        return super(Mooring_Loader,self).preProcessParams(row)


class BEDS_TS_Loader(TimeSeries_Loader):
    '''
    Benthic Event Detector timeSeries data.  Expects CF-1.6 timeSeries discrete sampling geometry type.
    '''
    include_names = ['XA', 'YA', 'ZA', 'XR', 'YR', 'ZR', 'PRESS', 'BED_DEPTH']

    def preProcessParams(self, row):
        '''
        Placeholder for any special preprocessing for Mooring data
        '''
        return super(BEDS_TS_Loader,self).preProcessParams(row)

#
# Helper methods that expose a common interface for executing the loaders for specific platforms
#
def runTrajectoryLoader(url, cName, cDesc, aName, pName, pColor, pTypeName, aTypeName, parmList, dbAlias, stride, plotTimeSeriesDepth=None, grdTerrain=None):
    '''
    Run the DAPloader for Generic AUVCTD trajectory data and update the Activity with 
    attributes resulting from the load into dbAlias. Designed to be called from script
    that loads the data.  Following the load important updates are made to the database.
    If a number vaue is given to plotTimeSeriesDepth then that Resource is added for each
    Parameter loaded; this gives instruction to the STOQS UI to also plot timeSries data
    in the Parameter tab.
    '''
    logger.debug("Instantiating Trajectory_Loader for url = %s", url)
    loader = Trajectory_Loader(
            url = url,
            campaignName = cName,
            campaignDescription = cDesc,
            dbAlias = dbAlias,
            activityName = aName,
            activitytypeName = aTypeName,
            platformName = pName,
            platformColor = pColor,
            platformTypeName = pTypeName,
            stride = stride,
            grdTerrain = grdTerrain)

    logger.debug("Setting include_names to %s", parmList)
    loader.include_names = parmList

    # Fix up legacy data files
    loader.auxCoords = {}
    if aName.find('_jhmudas_v1') != -1:
        for p in loader.include_names:
            loader.auxCoords[p] = {'time': 'time', 'latitude': 'latitude', 'longitude': 'longitude', 'depth': 'depth'}

    if plotTimeSeriesDepth:
        # Used first for BEDS where we want both trajectory and timeSeries plots - assumes starting depth of BED
        loader.plotTimeSeriesDepth = dict.fromkeys(parmList, plotTimeSeriesDepth)

    (nMP, path, parmCountHash, mind, maxd) = loader.process_data()
    logger.debug("Loaded Activity with name = %s", aName)

def runDoradoLoader(url, cName, cDesc, aName, pName, pColor, pTypeName, aTypeName, dbAlias, stride, grdTerrain=None):
    '''
    Run the DAPloader for Dorado AUVCTD trajectory data and update the Activity with 
    attributes resulting from the load into dbAlias. Designed to be called from script
    that loads the data.  Following the load important updates are made to the database.
    '''
    logger.debug("Instantiating Dorado_Loader for url = %s", url)
    loader = Dorado_Loader(
            url = url,
            campaignName = cName,
            campaignDescription = cDesc,
            dbAlias = dbAlias,
            activityName = aName,
            activitytypeName = aTypeName,
            platformName = pName,
            platformColor = pColor,
            platformTypeName = pTypeName,
            stride = stride,
            grdTerrain = grdTerrain)

    # Auxillary coordinates are the same for all include_names
    loader.auxCoords = {}
    for v in loader.include_names:
        loader.auxCoords[v] = {'time': 'time', 'latitude': 'latitude', 'longitude': 'longitude', 'depth': 'depth'}

    try:
        (nMP, path, parmCountHash, mind, maxd) = loader.process_data()
    except VariableMissingCoordinatesAttribute, e:
        logger.exception(e)
    else:
        logger.debug("Loaded Activity with name = %s", aName)

def runLrauvLoader(url, cName, cDesc, aName, pName, pColor, pTypeName, aTypeName, parmList, dbAlias, stride, startDatetime=None, endDatetime=None, grdTerrain=None):
    '''
    Run the DAPloader for Long Range AUVCTD trajectory data and update the Activity with 
    attributes resulting from the load into dbAlias. Designed to be called from script
    that loads the data.  Following the load important updates are made to the database.
    '''
    logger.debug("Instantiating Lrauv_Loader for url = %s", url)
    loader = Lrauv_Loader(
            url = url,
            campaignName = cName,
            campaignDescription = cDesc,
            dbAlias = dbAlias,
            activityName = aName,
            activitytypeName = aTypeName,
            platformName = pName,
            platformColor = pColor,
            platformTypeName = pTypeName,
            stride = stride,
            startDatetime = startDatetime,
            endDatetime = endDatetime,
            grdTerrain = grdTerrain)

    if parmList:
        logger.debug("Setting include_names to %s", parmList)
        loader.include_names = parmList

    loader.auxCoords = {}
    if aName.find('_Chl_') != -1:
        for p in loader.include_names:
            loader.auxCoords[p] = {'time': 'Time', 'latitude': 'latitude', 'longitude': 'longitude', 'depth': 'depth'}

    try:
        (nMP, path, parmCountHash, mind, maxd) = loader.process_data()
    except NoValidData, e:
        logger.warn(e)
    else:    
        logger.debug("Loaded Activity with name = %s", aName)

def runGliderLoader(url, cName, cDesc, aName, pName, pColor, pTypeName, aTypeName, parmList, dbAlias, stride, startDatetime=None, endDatetime=None, grdTerrain=None):
    '''
    Run the DAPloader for Spray Glider trajectory data and update the Activity with 
    attributes resulting from the load into dbAlias. Designed to be called from script
    that loads the data.  Following the load important updates are made to the database.
    '''
    logger.debug("Instantiating Glider_Loader for url = %s", url)
    loader = Glider_Loader(
            url = url,
            campaignName = cName,
            campaignDescription = cDesc,
            dbAlias = dbAlias,
            activityName = aName,
            activitytypeName = aTypeName,
            platformName = pName,
            platformColor = pColor,
            platformTypeName = pTypeName,
            stride = stride,
            startDatetime = startDatetime,
            endDatetime = endDatetime,
            grdTerrain = grdTerrain)

    if parmList:
        logger.debug("Setting include_names to %s", parmList)
        loader.include_names = parmList

    # Auxillary coordinates are the same for all include_names
    loader.auxCoords = {}
    if pTypeName == 'waveglider':
        #for v in loader.include_names:
        #    loader.auxCoords[v] = {'time': 'TIME', 'latitude': 'latitude', 'longitude': 'longitude', 'depth': 'depth'}
        pass
    elif pName.startswith('Slocum'):
        loader.auxCoords['u'] = {'time': 'time_uv', 'latitude': 'lat_uv', 'longitude': 'lon_uv', 'depth': 0.0}
        loader.auxCoords['v'] = {'time': 'time_uv', 'latitude': 'lat_uv', 'longitude': 'lon_uv', 'depth': 0.0}
        loader.auxCoords['temperature'] = {'time': 'time', 'latitude': 'lat', 'longitude': 'lon', 'depth': 'depth'}
        loader.auxCoords['salinity'] = {'time': 'time', 'latitude': 'lat', 'longitude': 'lon', 'depth': 'depth'}
        loader.auxCoords['density'] = {'time': 'time', 'latitude': 'lat', 'longitude': 'lon', 'depth': 'depth'}
        loader.auxCoords['fluorescence'] = {'time': 'time', 'latitude': 'lat', 'longitude': 'lon', 'depth': 'depth'}
        loader.auxCoords['oxygen'] = {'time': 'time', 'latitude': 'lat', 'longitude': 'lon', 'depth': 'depth'}
        loader.auxCoords['optical_backscatter700nm'] = {'time': 'time', 'latitude': 'lat', 'longitude': 'lon', 'depth': 'depth'}

    elif pName.startswith('SPRAY'):
        for p in loader.include_names:
            loader.auxCoords[p] = {'time': 'TIME', 'latitude': 'LATITUDE', 'longitude': 'LONGITUDE', 'depth': 'DEPTH'}
    elif pName.startswith('NPS'):
        for p in loader.include_names:
            loader.auxCoords[p] = {'time': 'TIME', 'latitude': 'LATITUDE', 'longitude': 'LONGITUDE', 'depth': 'DEPTH'}

    # Fred is now writing according to CF-1.6 and we can expect compliance with auxillary coordinate attribute specifications for future files

    try:
        (nMP, path, parmCountHash, mind, maxd) = loader.process_data()
    except VariableMissingCoordinatesAttribute, e:
        logger.exception(e)
    else:    
        logger.debug("Loaded Activity with name = %s", aName)

def runTimeSeriesLoader(url, cName, cDesc, aName, pName, pColor, pTypeName, aTypeName, parmList, dbAlias, stride, startDatetime=None, endDatetime=None):
    '''
    Run the DAPloader for Generic CF Metadata timeSeries featureType data. 
    Following the load important updates are made to the database.
    '''
    logger.debug("Instantiating TimeSeries_Loader for url = %s", url)
    loader = TimeSeries_Loader(
            url = url,
            campaignName = cName,
            campaignDescription = cDesc,
            dbAlias = dbAlias,
            activityName = aName,
            activitytypeName = aTypeName,
            platformName = pName,
            platformColor = pColor,
            platformTypeName = pTypeName,
            stride = stride,
            startDatetime = startDatetime,
            endDatetime = endDatetime)

    if parmList:
        logger.debug("Setting include_names to %s", parmList)
        loader.include_names = parmList

    (nMP, path, parmCountHash, mind, maxd) = loader.process_data()
    logger.debug("Loaded Activity with name = %s", aName)

def runMooringLoader(url, cName, cDesc, aName, pName, pColor, pTypeName, aTypeName, parmList, dbAlias, stride, startDatetime=None, endDatetime=None):
    '''
    Run the DAPloader for OceanSites formatted Mooring Station data and update the Activity with 
    attributes resulting from the load into dbAlias. Designed to be called from script
    that loads the data.  Following the load important updates are made to the database.
    '''
    logger.debug("Instantiating Mooring_Loader for url = %s", url)
    loader = Mooring_Loader(
            url = url,
            campaignName = cName,
            campaignDescription = cDesc,
            dbAlias = dbAlias,
            activityName = aName,
            activitytypeName = aTypeName,
            platformName = pName,
            platformColor = pColor,
            platformTypeName = pTypeName,
            stride = stride,
            startDatetime = startDatetime,
            endDatetime = endDatetime)

    if parmList:
        logger.debug("Setting include_names to %s", parmList)
        loader.include_names = parmList

    loader.auxCoords = {}
    if url.endswith('_CMSTV.nc'):
        # Special for combined file which has different coordinates for different variables
        for v in loader.include_names:
            if v in ['eastward_sea_water_velocity_HR', 'northward_sea_water_velocity_HR']:
                loader.auxCoords[v] = {'time': 'hr_time_adcp', 'latitude': 'latitude', 'longitude': 'longitude', 'depth': 'HR_DEPTH_adcp'}
            elif v in ['SEA_WATER_SALINITY_HR', 'SEA_WATER_TEMPERATURE_HR']:
                loader.auxCoords[v] = {'time': 'hr_time_ts', 'latitude': 'LATITUDE', 'longitude': 'LONGITUDE', 'depth': 'DEPTH'}
            elif v in ['SW_FLUX_HR', 'AIR_TEMPERATURE_HR', 'EASTWARD_WIND_HR', 'NORTHWARD_WIND_HR', 'WIND_SPEED_HR']:
                loader.auxCoords[v] = {'time': 'hr_time_met', 'latitude': 'Latitude', 'longitude': 'Longitude', 'depth': 'HR_DEPTH_met'}
            else:
                logger.error('Do not have an auxCoords assignment for variable %s in include_names', v)
    elif url.find('_hs2_') != -1:
        # Special for fluorometer on M1 - the HS2
        for v in loader.include_names:
            if v in ['bb470', 'bb676', 'fl676']:
                loader.auxCoords[v] = {'time': 'esecs', 'latitude': 'Latitude', 'longitude': 'Longitude', 'depth': 'NominalDepth'}
    else:
        # Auxillary coordinates are the same for all include_names for _TS and _M files
        for v in loader.include_names:
            loader.auxCoords[v] = {'time': 'TIME', 'latitude': 'LATITUDE', 'longitude': 'LONGITUDE', 'depth': 'DEPTH'}

    try:
        (nMP, path, parmCountHash, mind, maxd) = loader.process_data()
        logger.debug("Loaded Activity with name = %s", aName)
    except NoValidData, e:
        logger.warning(e)


if __name__ == '__main__':
    # A nice test data load for a northern Monterey Bay survey  
    baseUrl = 'http://odss.mbari.org/thredds/dodsC/dorado/'             # NCML to make salinity.units = "1"
    file = 'Dorado389_2010_300_00_300_00_decim.nc'
    stride = 1000       # Make large for quicker runs, smaller for denser data
    dbAlias = 'default'

    runDoradoLoader(baseUrl + file, 'Test Load', file, 'dorado', 'auv', 'AUV Mission', dbAlias, stride)

    # See loaders/CANON/__init__.py for more examples of how these loaders are used

