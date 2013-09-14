#!/usr/bin/env python
__author__    = 'Mike McCann,Duane Edgington,Reiko Michisaki'
__copyright__ = '2013'
__license__   = 'GPL v3'
__contact__   = 'duane at mbari.org'

__doc__ = '''

loader for ESP CANON activities in September 2013

Mike McCann; Modified by Duane Edgington and Reiko Michisaki
MBARI 02 September 2013

@var __date__: Date of last svn commit
@undocumented: __doc__ parser
@status: production
@license: GPL
'''

import os
import sys
import datetime  # needed for glider data
import time      # for startdate, enddate args
os.environ['DJANGO_SETTINGS_MODULE']='settings'
project_dir = os.path.dirname(__file__)

# the next line makes it possible to find CANON
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../"))  # this makes it possible to find CANON, one directory up

from CANON import CANONLoader
       
# building input data sources object
#cl = CANONLoader('stoqs_september2011', 'CANON - September 2011')
cl = CANONLoader('stoqs_september2013', 'CANON - September 2013')

# default location of thredds and dods data:
cl.tdsBase = 'http://odss.mbari.org/thredds/'
cl.dodsBase = cl.tdsBase + 'dodsC/'

# Set start and end dates for mooring, twice per day.  In the morning and afternoon.
#t =time.strptime("2013-09-10 0:01", "%Y-%m-%d %H:%M")
##startdate=t[:6]
ts=time.time()-(13*60*60)
st=datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')
t=time.strptime(st,"%Y-%m-%d %H:%M")
startdate=t[:6]
t =time.strptime("2013-10-29 0:01", "%Y-%m-%d %H:%M")
enddate=t[:6]
print startdate, enddate

######################################################################
#  ESP MOORINGS
######################################################################
cl.bruce_moor_base = cl.dodsBase + 'CANON_september2013/Platforms/Moorings/ESP_Bruce/NetCDF/'
cl.bruce_moor_files = ['Bruce_ctd.nc']
cl.bruce_moor_parms = [ 'TEMP','PSAL','chl','xmiss','oxygen',
                   ]
cl.bruce_moor_startDatetime = datetime.datetime(*startdate[:])
cl.bruce_moor_endDatetime = datetime.datetime(*enddate[:])

cl.mack_moor_base = cl.dodsBase + 'CANON_september2013/Platforms/Moorings/ESP_Mack/NetCDF/'
cl.mack_moor_files = ['Mack_ctd.nc']
cl.mack_moor_parms = [ 'TEMP','PSAL','chl','xmiss','oxygen',
                   ]
cl.mack_moor_startDatetime = datetime.datetime(*startdate[:])
cl.mack_moor_endDatetime = datetime.datetime(*enddate[:])

cl.process_command_line()

if cl.args.test:
    cl.loadBruceMoor(stride=1)
    cl.loadMackMoor(stride=1)

elif cl.args.optimal_stride:
    cl.loadBruceMoor(stride=1)
    cl.loadMackMoor(stride=1)

else:
    cl.loadBruceMoor(stride=1)
    cl.loadMackMoor(stride=1)
