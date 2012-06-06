#!/usr/bin/env python

__author__ = "Mike McCann"
__copyright__ = "Copyright 2012, MBARI"
__license__ = "GPL"
__maintainer__ = "Mike McCann"
__email__ = "mccann at mbari.org"
__doc__ = '''

Script to read data from CSV formatted data from the Liquid Robotics Waveglider
platform and write them to netCDF files.  There are 3 separate time axes for this
data set:

    1. CTD & GPS time from the gpctd file
    2. PCO2 time from the _pco2 file
and
    3. pH time for the 6 Durafet pH sensor data in the _pco2 file
       (Though these are on the same line, they are each successively 10 minutes 
       earlier than PCO2 Timestamp.)

Use the conventions for Trajectory feature type and write as much metdata as possible.

This script is meant to preserve the data identically as it was reported to us from 
liquid Robotics.  Any merging should be done afterwards; having the data in NetCDF
should ease any merging process.

Mike McCann
MBARI 5 June 2012

@var __date__: Date of last svn commit
@undocumented: __doc__ parser
@author: __author__
@license: __license__
'''

import os
import sys
import csv
import time
import coards
import datetime
import numpy as np
from pupynere import netcdf_file

class ParserWriter(object):
    '''
    Handle all information needed to parse LR Waveglider CSV files and produce 
    NetCDF for each of them
    '''

    def __init__(self, parentDir):
        self.parentDir = parentDir
        

    def write_gpctd(self, inFile='waveglider_gpctd_WG.txt', outFile='waveglider_gpctd_WG.nc'):
        '''
        Read in records from one of the waveglider data files and write out as NetCDF.  The records look like:

        GPCTD Timestamp, Latitude, Longitude, Pressure(decibars), Temperature(degrees C), Salinity(PSU), Conductivity(S/m), Dissolved Oxygen(frequency), Dissolved Oxygen(mL/L)
        2012-05-21 20:10:00, 36.7989, -121.8609, 0.280, 12.169, 33.764, 3.889, 4390.700,  5.374
        2012-05-21 20:10:10, 36.7989, -121.8609, 0.330, 12.148, 33.779, 3.888, 4397.800,  5.387
        '''

        # Initialize lists for the data to be parsed and written
        esec_list = []
        lat_list = []
        lon_list = []
        dep_list = []
        tem_list = []
        sal_list = []
        do_list = []

        # Read data in from the input file
        reader = csv.DictReader(open(os.path.join(self.parentDir, inFile)))
        for r in reader:
            gmtDTString = r['GPCTD Timestamp']
            tt = time.strptime(gmtDTString, '%Y-%m-%d %H:%M:%S')
            diff = datetime.datetime(*tt[:6]) - datetime.datetime(1970,1,1,0,0,0)
        
            esec_list.append(diff.days * 86400 + diff.seconds)
            lat_list.append(r[' Latitude'])
            lon_list.append(r[' Longitude'])
            dep_list.append(r[' Pressure(decibars)'])        # decibars is darn close to meters at the surface
        
            tem_list.append(r[' Temperature(degrees C)'])
            sal_list.append(r[' Salinity(PSU)'])
            do_list.append(r[' Dissolved Oxygen(mL/L)'])

        # Create the NetCDF file
        self.ncFile = netcdf_file(outFile, 'w')
        self.outFile = outFile

        # Trajectory dataset, time is the only netCDF dimension
        self.ncFile.createDimension('TIME', len(esec_list))
        self.time = self.ncFile.createVariable('TIME', 'float64', ('TIME',))
        self.time.units = 'seconds since 1970-01-01'
        self.time[:] = esec_list

        # Record Variables - coordinates for trajectory - save in the instance and use for metadata generation
        self.latitude = self.ncFile.createVariable('latitude', 'float64', ('TIME',))
        self.latitude.long_name = 'LATITUDE'
        self.latitude.standard_name = 'latitude'
        self.latitude.units = 'degree_north'
        self.latitude[:] = lat_list

        self.longitude = self.ncFile.createVariable('longitude', 'float64', ('TIME',))
        self.longitude.long_name = 'LONGITUDE'
        self.longitude.standard_name = 'longitude'
        self.longitude.units = 'degree_east'
        self.longitude[:] = lon_list

        self.depth = self.ncFile.createVariable('depth', 'float64', ('TIME',))
        self.depth.long_name = 'DEPTH'
        self.depth.standard_name = 'depth'
        self.depth.units = 'm'
        self.depth[:] = dep_list

        # Record Variables - CTD Data
        temp = self.ncFile.createVariable('TEMP', 'float64', ('TIME',))
        temp.long_name = 'Temperature'
        temp.standard_name = 'sea_water_temperature'
        temp.units = 'Celsius'
        temp[:] = tem_list

        sal = self.ncFile.createVariable('PSAL', 'float64', ('TIME',))
        sal.long_name = 'Salinity'
        sal.standard_name = 'sea_water_salinity'
        sal[:] = sal_list

        do = self.ncFile.createVariable('oxygen', 'float64', ('TIME',))
        do.long_name = 'Dissolved Oxygen'
        do.units = 'ml/l'
        do[:] = do_list

        self.add_global_metadata()

        self.ncFile.close()

        # End write_gpctd()

    def write_pco2(self, inFile='waveglider_pco2_WG.txt', outFile='waveglider_pco2_WG.nc'):
        '''
        Read in records from one of the waveglider data files and write out as NetCDF.  The records are
        really long and ugly - the header for the file is expressed in the pco2_var list.  This method 
        builds the NetCDF variables dynamically using the Python 'exec' method.
        '''

        esec_list = []
        pco2_vars = [   'Latitude', 'Longitude', 'EquilPumpOn pco2', 'EquilPumpOn Temp', 'EquilPumpOn Pressure', 
                'EquilPumpOff pco2', 'EquilPumpOff Temp', 'EquilPumpOff Pressure', 'EquilPumpOff Humidity', 
                'ZeroPumpOn pco2', 'ZeroPumpOn Temp', 'ZeroPumpOn Pressure', 'ZeroPumpOff pco2', 'ZeroPumpOff Temp', 
                'ZeroPumpOff Pressure', 'AirPumpOn pco2', 'AirPumpOn Temp', 'AirPumpOn Pressure', 'AirPumpOff pco2', 
                'AirPumpOff Temp', 'AirPumpOff Pressure', 'AirPumpOff Humidity', 'StandardFlowOn Pressure', 
                'StandardFlowOff pco2', 'StandardFlowOff Temp', 'StandardFlowOff Pressure', 
                'StandardFlowOff pco2 Humidity', 'Durafet pH 1', 'Durafet pH 2', 'Durafet pH 3', 'Durafet pH 4', 
                'Durafet pH 5', 'Durafet pH 6', 'Can Humidity'
                    ]

        reader = csv.DictReader(open(os.path.join(self.parentDir, inFile)))
        for r in reader:
            gmtDTString = r['PCO2 Timestamp']
            tt = time.strptime(gmtDTString, '%Y-%m-%d %H:%M:%S')
            diff = datetime.datetime(*tt[:6]) - datetime.datetime(1970,1,1,0,0,0)
        
            esec_list.append(diff.days * 86400 + diff.seconds)
        
            for v in pco2_vars:
                ncVar = v.replace(' ', '_', 42)
                try:
                    exec "%s_list.append(r[' %s'])" % (ncVar, v, )
                except NameError:
                    exec '%s_list = []' % ncVar
                    exec "%s_list.append(r[' %s'])" % (ncVar, v, )

        # Create the NetCDF file
        self.ncFile = netcdf_file(outFile, 'w')
        self.outFile = outFile

        # Trajectory dataset, time is the only netCDF dimension
        self.ncFile.createDimension('TIME', len(esec_list))

        self.time = self.ncFile.createVariable('TIME', 'float64', ('TIME',))
        self.time.units = 'seconds since 1970-01-01'
        self.time[:] = esec_list

        # PCO2 variables 
        for v in pco2_vars:
            ncVar = v.replace(' ', '_', 42)
            # Only Latitude, Longitude, Depth, and Time variables are upper case to match other Glider data
            if v == 'Latitude' or v == 'Longitude':
                exec "self.%s = self.ncFile.createVariable('%s', 'float64', ('TIME',))" % (ncVar.lower(), ncVar.upper(), )
            else:
                exec "self.%s = self.ncFile.createVariable('%s', 'float64', ('TIME',))" % (ncVar.lower(), ncVar, )
            exec "self.%s.long_name = '%s'" % (ncVar.lower(), v, )
            exec "self.%s[:] = %s_list" % (ncVar.lower(), ncVar, )

        # Fudge up a depth variable with a value of zero
        self.depth = self.ncFile.createVariable('DEPTH', 'float64', ('TIME',))
        self.depth.long_name = 'Depth'
        self.depth.standard_name = 'depth'
        self.depth.units = 'm'
        self.depth[:] = np.zeros(len(self.time[:]))

        self.add_global_metadata()

        self.ncFile.close()

        # End write_pco2()

    def add_global_metadata(self):
        '''
        This is the main advantage of using a class for these methods.  This method uses the
        instance variables to write metadata specific for the data that are written.
        '''

        iso_now = datetime.datetime.now().isoformat()

        self.ncFile.title = ''
        self.ncFile.netcdf_version = '3.6'
        self.ncFile.Convention = 'CF-1.4'
        self.ncFile.date_created = iso_now
        self.ncFile.date_update = iso_now
        self.ncFile.date_modified = iso_now
        self.ncFile.cdm_data_type = 'trajectory'
        self.ncFile.CF_featureType = 'trajectory'
        self.ncFile.data_mode = 'R'
        self.ncFile.geospatial_lat_min = np.min(self.latitude[:])
        self.ncFile.geospatial_lat_max = np.max(self.latitude[:])
        self.ncFile.geospatial_lon_min = np.min(self.longitude[:])
        self.ncFile.geospatial_lon_max = np.max(self.longitude[:])
        self.ncFile.geospatial_lat_units = 'degree_north'
        self.ncFile.geospatial_lon_units = 'degree_east'

        self.ncFile.geospatial_vertical_min= np.min(self.depth[:])
        self.ncFile.geospatial_vertical_max= np.max(self.depth[:])
        self.ncFile.geospatial_vertical_units = 'm'
        self.ncFile.geospatial_vertical_positive = 'down'

        self.ncFile.time_coverage_start = coards.from_udunits(self.time[0], self.time.units).isoformat()
        self.ncFile.time_coverage_end = coards.from_udunits(self.time[-1], self.time.units).isoformat()

        self.ncFile.distribution_statement = 'Any use requires prior approval from the MBARI CANON PI: Dr. Francisco Chavez'
        self.ncFile.license = self.ncFile.distribution_statement
        self.ncFile.history = 'Created by "%s" on %s' % (' '.join(sys.argv), iso_now,)


if __name__ == '__main__':

    ctd = ParserWriter(parentDir='.')
    ctd.write_gpctd()
    print "Wrote %s" % ctd.outFile

    pco2 = ParserWriter(parentDir='.')
    pco2.write_pco2()
    print "Wrote %s" % ctd.outFile

