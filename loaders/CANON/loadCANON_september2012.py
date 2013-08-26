#!/usr/bin/env python
__author__    = 'Mike McCann'
__copyright__ = '2012'
__license__   = 'GPL v3'
__contact__   = 'mccann at mbari.org'

__doc__ = '''
Master loader for all September 2012 CANON activities.  

Mike McCann
MBARI 6 September AUgust 2012

@var __date__: Date of last svn commit
@undocumented: __doc__ parser
@status: production
@license: GPL
'''

import os
import sys
import datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../"))      # So that CANON is found

from CANON import CANONLoader

cl = CANONLoader('stoqs_september2012', 'CANON - September 2012')

# Aboard the Flyer use malibu's VSAT IP address:
cl.tdsBase = 'http://odss.mbari.org/thredds/'       
cl.dodsBase = cl.tdsBase + 'dodsC/'       

# 2-second decimated dorado data
# http://192.168.111.177:8080/thredds/dodsC/CANON_september2012/dorado/Dorado389_2012_258_00_258_00_decim.nc
cl.dorado_base = cl.dodsBase + 'CANON_september2012/dorado/'
cl.dorado_files = [ 
                    'Dorado389_2012_256_00_256_00_decim.nc',
                    'Dorado389_2012_257_01_257_01_decim.nc',
                    'Dorado389_2012_258_00_258_00_decim.nc',
                  ]

# Realtime telemetered (_r_) daphne data - insert '_r_' to not load the files
##cl.daphne_base = 'http://aosn.mbari.org/lrauvtds/dodsC/lrauv/daphne/2012/'
cl.daphne_base = cl.dodsBase + 'CANON_september2012/lrauv/daphne/realtime/sbdlogs/2012/201209/'
cl.daphne_files = [ 
# NoValidData                    '20120910T142840/shore.nc',
# NoValidData                    '20120910T143107/shore.nc',
                    '20120910T221418/shore.nc',
# NoValidData                    '20120911T005835/shore.nc',
                    '20120911T031754/shore.nc',
# NoValidData                    '20120911T105509/shore.nc',
                    '20120911T215648/shore.nc',
                  ]
cl.daphne_parms = [ 'platform_battery_charge', 'sea_water_temperature', 'downwelling_photosynthetic_photon_flux_in_sea_water',
                    'mass_concentration_of_oxygen_in_sea_water', 'mass_concentration_of_chlorophyll_in_sea_water']

# Postrecovery full-resolution (_d_) daphne data - insert '_d_' for delayed-mode to not load the data
cl.daphne_d_base = 'http://elvis.shore.mbari.org:8080/thredds/dodsC/lrauv/daphne/2012/'
cl.daphne_d_files = [ 
                  ]
cl.daphne_d_parms = [ 'sea_water_temperature', 'sea_water_salinity', 'sea_water_density', 'volume_scattering_470_nm', 'volume_scattering_650_nm',
                    'volume_scattering_650_nm', 'mass_concentration_of_oxygen_in_sea_water', 'mole_concentration_of_nitrate_in_sea_water',
                    'mass_concentration_of_chlorophyll_in_sea_water']

# Realtime telemetered (_r_) tethys data - insert '_r_' to not load the files
##cl.tethys_base = 'http://aosn.mbari.org/lrauvtds/dodsC/lrauv/tethys/2012/'                    # Tethys realtime
cl.tethys_base = cl.dodsBase + 'CANON_september2012/lrauv/tethys/realtime/sbdlogs/2012/201209/'
cl.tethys_files = [ 
                    '20120909T152301/shore.nc',
                    '20120910T190223/shore.nc',
                    '20120911T125230/shore.nc',
                    '20120912T003318/shore.nc',
                    '20120912T015450/shore.nc',
                    '20120912T142126/shore.nc',
                    '20120915T030845/shore.nc',
                    '20120917T025522/shore.nc',
                    '20120917T111359/shore.nc',
                    '20120917T123308/shore.nc',
                    '20120917T150614/shore.nc',
                    '20120917T151928/shore.nc',
                  ]
cl.tethys_parms = [ 'platform_battery_charge', 'sea_water_temperature', 'downwelling_photosynthetic_photon_flux_in_sea_water',
                    'mass_concentration_of_oxygen_in_sea_water', 'mass_concentration_of_chlorophyll_in_sea_water', 'mole_concentration_of_nitrate_in_sea_water']

# Postrecovery full-resolution tethys data - insert '_d_' for delayed-mode to not load the data
cl.tethys_d_base = 'http://elvis.shore.mbari.org:8080/thredds/dodsC/lrauv/tethys/2012/'
cl.tethys_d_files = [ 
                  ]

cl.tethys_d_parms = [ 'sea_water_temperature', 'sea_water_salinity', 'sea_water_density', 'volume_scattering_470_nm', 'volume_scattering_650_nm',
                    'volume_scattering_650_nm', 'mass_concentration_of_oxygen_in_sea_water', 'mole_concentration_of_nitrate_in_sea_water',
                    'mass_concentration_of_chlorophyll_in_sea_water']

cl.fulmar_base = []
cl.fulmar_files = []
cl.fulmar_parms = []

# Spray glider - for just the duration of the campaign
cl.l_662_base = 'http://www.cencoos.org/thredds/dodsC/gliders/Line66/'
cl.l_662_files = ['OS_Glider_L_662_20120816_TS.nc']
cl.l_662_parms = ['TEMP', 'PSAL', 'FLU2']
cl.l_662_startDatetime = datetime.datetime(2012, 9, 10)
cl.l_662_endDatetime = datetime.datetime(2012, 9, 20)

# Liquid Robotics Waveglider
cl.waveglider_base = cl.dodsBase + 'CANON_september2012/waveglider/'
cl.waveglider_files = [ 'waveglider_gpctd_WG.nc' ]
cl.waveglider_parms = [ 'TEMP', 'PSAL', 'oxygen' ]
cl.waveglider_startDatetime = datetime.datetime(2012, 8, 31, 18, 47, 0)
cl.waveglider_endDatetime = datetime.datetime(2012, 9, 25, 16, 0, 0)

# MBARI ESPdrift
cl.espdrift_base = cl.dodsBase + 'CANON_september2012/misc/ESPdrift/'
cl.espdrift_files = [ 
                        'ESP_ctd.nc',
                        'ESP_isus.nc',
                      ]
cl.espdrift_parms = [ 'TEMP', 'PSAL', 'chl', 'chlini', 'no3' ]

# Western Flyer Underway CTD
cl.wfuctd_base = cl.dodsBase + 'CANON_september2012/wf/uctd/'
cl.wfuctd_files = [ 
        'c0912m01.nc', 'c0912m02.nc', 'c0912m03.nc', 'c0912m04.nc', 'c0912m05.nc', 'c0912m06.nc', 
        'c0912m07.nc', 'c0912m08.nc', 'c0912m09.nc', 'c0912m10.nc', 'c0912m11.nc', 'c0912m12.nc', 
        'c0912m13.nc', 'c0912m14.nc', 'c0912m15.nc', 'c0912m16.nc', 'c0912m17.nc', 'c0912m18.nc', 
        'c0912m19.nc', 
                      ]
cl.wfuctd_parms = [ 'TEMP', 'PSAL', 'xmiss', 'wetstar' ]

# Western Flyer Profile CTD
cl.pctdDir = 'CANON_september2012/wf/pctd/'
cl.wfpctd_base = cl.dodsBase + cl.pctdDir
cl.wfpctd_files = [ 
'c0912c01up.nc', 'c0912c02.nc', 'c0912c03.nc', 'c0912c04.nc', 'c0912c05.nc', 'c0912c06.nc', 
'c0912c07.nc', 'c0912c08.nc', 'c0912c09.nc', 'c0912c10.nc', 'c0912c11.nc', 'c0912c12.nc', 
'c0912c13.nc', 'c0912c14.nc', 'c0912c15.nc', 'c0912c16.nc', 'c0912c17.nc', 'c0912c18.nc', 
'c0912c19.nc', 'c0912c20.nc', 'c0912c21.nc', 'c0912c22.nc', 'c0912c23.nc', 'c0912c24.nc', 
'c0912c25.nc', 'c0912c26.nc', 'c0912c27.nc', 'c0912c28.nc', 'c0912c29.nc', 'c0912c30.nc', 
'c0912c31.nc', 'c0912c32.nc', 'c0912c33.nc', 'c0912c34.nc', 'c0912c35.nc', 'c0912c36.nc', 
'c0912c37.nc', 'c0912c38.nc', 'c0912c39.nc', 'c0912c40.nc', 'c0912c41.nc', 'c0912c42.nc', 
'c0912c43.nc', 'c0912c44.nc', 'c0912c45.nc', 'c0912c46.nc', 'c0912c47.nc', 'c0912c48.nc', 
'c0912c49.nc', 'c0912c50.nc', 'c0912c51.nc', 'c0912c52.nc', 'c0912c53.nc', 'c0912c54.nc',
                      ]
cl.wfpctd_parms = [ 'TEMP', 'PSAL', 'xmiss', 'ecofl' ]

# Spray glider - for just the duration of the campaign
cl.l_662_base = 'http://www.cencoos.org/thredds/dodsC/gliders/Line66/'
cl.l_662_files = ['OS_Glider_L_662_20120816_TS.nc']
cl.l_662_parms = ['TEMP', 'PSAL', 'FLU2']
cl.l_662_startDatetime = datetime.datetime(2012, 9, 1)
cl.l_662_endDatetime = datetime.datetime(2012, 9, 21)

# Mooring M1 Combined file produced by DPforSSDS processing - for just the duration of the campaign
cl.m1_base = 'http://dods.mbari.org/opendap/data/ssdsdata/deployments/m1/201202/'
cl.m1_files = ['OS_M1_20120222hourly_CMSTV.nc']
cl.m1_parms = [ 'eastward_sea_water_velocity_HR', 'northward_sea_water_velocity_HR',
                'SEA_WATER_SALINITY_HR', 'SEA_WATER_TEMPERATURE_HR', 'SW_FLUX_HR', 'AIR_TEMPERATURE_HR',
                'EASTWARD_WIND_HR', 'NORTHWARD_WIND_HR', 'WIND_SPEED_HR'
              ]
cl.m1_startDatetime = datetime.datetime(2012, 9, 15)        # Good data starts on the 15th
cl.m1_endDatetime = datetime.datetime(2012, 9, 21)

# SubSample data files from /mbari/BOG_Archive/ReportsForSTOQS/C0912/ copied to local BOG_Data dir
cl.subsample_csv_base = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'BOG_Data/C0912/')
cl.subsample_csv_files = [
                            'STOQS_C0912_ALTIMETER.csv',
                            'STOQS_C0912_CARBON_GFF.csv',
                            'STOQS_C0912_CHL_1U.csv',
                            'STOQS_C0912_CHL_5U.csv',
                            'STOQS_C0912_CHLA.csv',
                            'STOQS_C0912_CHL_GFF.csv',
                            'STOQS_C0912_COND2.csv',
                            'STOQS_C0912_CONDUCT.csv',
                            'STOQS_C0912_FLUOR.csv',
                            'STOQS_C0912_NH4.csv',
                            'STOQS_C0912_NO2.csv',
                            'STOQS_C0912_NO3.csv',
                            'STOQS_C0912_OXY_ML.csv',
                            'STOQS_C0912_OXY_PS.csv',
                            'STOQS_C0912_PAR4PI.csv',
                            'STOQS_C0912_PARCOS.csv',
                            'STOQS_C0912_PHAEO_1U.csv',
                            'STOQS_C0912_PHAEO_5U.csv',
                            'STOQS_C0912_PHAEO_GFF.csv',
                            'STOQS_C0912_PO4.csv',
                            'STOQS_C0912_POT_TMP2.csv',
                            'STOQS_C0912_POT_TMP.csv',
                            'STOQS_C0912_SAL2.csv',
                            'STOQS_C0912_SAL.csv',
                            'STOQS_C0912_SIG_T.csv',
                            'STOQS_C0912_SIO4.csv',
                            'STOQS_C0912_TEMP2.csv',
                            'STOQS_C0912_TMP.csv',
                            'STOQS_C0912_TRANSBEAM.csv',
                            'STOQS_C0912_TRANSMISS.csv',
                         ]


# Execute the load
cl.process_command_line()

if cl.args.test:
    cl.loadDorado(stride=100)
    cl.loadWaveglider(stride=100)
    cl.loadDaphne(stride=10)
    cl.loadTethys(stride=10)
    cl.loadESPdrift(stride=10)
    cl.loadWFuctd(stride=10)
    cl.loadWFpctd(stride=10)
    cl.loadL_662(stride=100)
    cl.loadM1(stride=2)
    cl.loadSubSamples()

elif cl.args.optimal_stride:
    cl.loadDorado(stride=2)
    cl.loadWaveglider(stride=1)
    cl.loadDaphne(stride=1)
    cl.loadTethys(stride=1)
    cl.loadESPdrift(stride=1)
    cl.loadWFuctd(stride=1)
    cl.loadWFpctd(stride=1)
    cl.loadL_662(stride=1)
    cl.loadM1(stride=1)
    cl.loadSubSamples()

else:
    cl.stride = cl.args.stride
    cl.loadDorado()
    cl.loadWaveglider()
    cl.loadDaphne()
    cl.loadTethys()
    cl.loadESPdrift()
    cl.loadWFuctd()
    cl.loadWFpctd()
    cl.loadL_662()
    cl.loadM1()
    cl.loadSubSamples()

