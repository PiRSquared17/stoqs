#!/usr/bin/env python

__author__ = "Mike McCann"
__copyright__ = "Copyright 2013, MBARI"
__license__ = "GPL"
__maintainer__ = "Mike McCann"
__email__ = "mccann at mbari.org"
__status__ = "Development"
__doc__ = '''

Script to query the database for measured parameters from the same instantpoint and to
make scatter plots of temporal segments of the data.  A simplified trackline of the
trajectory data and the start time of the temporal segment are added to each plot.

Make use of STOQS metadata to make it as simple as possible to use this script for
different platforms, parameters, and campaigns.

Mike McCann
MBARI Dec 6, 2013

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

import re
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.dates import DAILY
from datetime import datetime, timedelta
from django.contrib.gis.geos import LineString, Point
from utils.utils import round_to_n
from textwrap import wrap
from mpl_toolkits.basemap import Basemap
import matplotlib.gridspec as gridspec

from contrib.analysis import BiPlot, NoPPDataException, NoTSDataException


class PlatformsBiPlot(BiPlot):
    '''
    Make customized BiPlots (Parameter Parameter plots) for platforms from STOQS.
    '''

    def ppSubPlot(self, x, y, platform, color, xParm, yParm, ax, startTime):
        '''
        Given names of platform, x & y paramters add a subplot to figure fig.
        '''

        xmin, xmax, xUnits = self._getAxisInfo(platform, xParm)
        ymin, ymax, yUnits = self._getAxisInfo(platform, yParm)

        # Make the plot 
        ax.set_xlim(round_to_n(xmin, 1), round_to_n(xmax, 1))
        ax.set_ylim(round_to_n(ymin, 1), round_to_n(ymax, 1))

        if self.args.xLabel == '':
            ax.set_xticks([])
        elif self.args.xLabel:
            ax.set_xlabel(self.args.xLabel)
        else:
            ax.set_xlabel('%s (%s)' % (xParm, xUnits))

        if self.args.yLabel == '':
            ax.set_yticks([])
        elif self.args.yLabel:
            ax.set_ylabel(self.args.yLabel)
        else:
            ax.set_ylabel('%s (%s)' % (yParm, yUnits))

        ax.scatter(x, y, marker='.', s=10, c='k', lw = 0, clip_on=True)
        ax.text(0.0, 1.0, platform, transform=ax.transAxes, color=color, horizontalalignment='left', verticalalignment='top')

        return ax

    def timeSubPlot(self, platformDTHash, ax1, allActivityStartTime, allActivityEndTime, startTime, endTime, swrTS):
        '''
        Make subplot of depth time series for all the platforms and highlight the time range
        '''
        for pl, ats in platformDTHash.iteritems():
            color = self._getColor(pl)
            for a, ts in ats.iteritems():
                datetimeList = []
                depths = []
                for ems, d in ts:
                    datetimeList.append(datetime.utcfromtimestamp(ems/1000.0))
                    depths.append(d)
           
                ax1.plot_date(matplotlib.dates.date2num(datetimeList), depths, '-', c=color, alpha=0.2)

        # Highlight the selected time extent
        ax1.axvspan(*matplotlib.dates.date2num([startTime, endTime]), facecolor='k', alpha=0.1)  

        if self.args.minDepth is not None:
            ax1.set_ylim(bottom=self.args.minDepth)
        if self.args.maxDepth:
            ax1.set_ylim(top=self.args.maxDepth)
        ax1.set_ylim(ax1.get_ylim()[::-1])

        if swrTS:
            # Plot short wave radiometer data
            if self.args.verbose: print 'Plotting swrTS...'
            ax2 = ax1.twinx()
            ax2.plot_date(matplotlib.dates.date2num(swrTS[0]), swrTS[1], '-', c='black', alpha=0.5)
            ax2.set_ylabel('SWR (W/m^2)')
            plt.locator_params(axis='y', nbins=3)
        
        ax1.set_xlabel('Time (GMT)')
        ax1.set_ylabel('Depth (m)')
        loc = ax1.xaxis.get_major_locator()
        loc.maxticks[DAILY] = 4

        return ax1

    def spatialSubPlot(self, platformLineStringHash, ax, e, resolution='l'):
        '''
        Make subplot of tracks for all the platforms within the time range. If self.args.coastlines then full resolution
        coastlines will be draw - significantly increasing execution time.
        '''
        if self.args.coastlines:
            resolution='f'
        m = Basemap(llcrnrlon=e[0], llcrnrlat=e[1], urcrnrlon=e[2], urcrnrlat=e[3], projection='cyl', resolution=resolution, ax=ax)
 
        for pl, LS in platformLineStringHash.iteritems():
            x,y = zip(*LS)
            m.plot(x, y, '-', c=self._getColor(pl))

        if self.args.coastlines:
            m.drawcoastlines()
        m.drawmapboundary()
        m.drawparallels(np.linspace(e[1],e[3],num=3), labels=[True,False,False,False])
        m.drawmeridians(np.linspace(e[0],e[2],num=3), labels=[False,False,False,True])

        return ax

    def getFilename(self, startTime):
        '''
        Construct plot file name
        '''
        if self.args.title:
            p = re.compile('[\s()]')
            fnTempl = p.sub('_', self.args.title) + '_{time}'
        else:
            fnTempl= 'platforms_{time}' 
            
        fileName = fnTempl.format(time=startTime.strftime('%Y%m%dT%H%M'))
        wcName = fnTempl.format(time=r'*')
        wcName = os.path.join(self.args.plotDir, self.args.plotPrefix + wcName)
        if self.args.daytime:
            fileName += '_day'
            wcName += '_day'
        if self.args.nighttime:
            fileName += '_night'
            wcName += '_night'
        fileName += '.png'

        fileName = os.path.join(self.args.plotDir, self.args.plotPrefix + fileName)

        return fileName, wcName

    def makePlatformsBiPlots(self):
        '''
        Cycle through all the platforms & parameters (there will be more than one) and make the correlation plots
        for the interval as subplots on the same page.  Include a map overview and timeline such that if a movie 
        is made of the resulting images a nice story is told.  Layout of the plot page is like:

         D  +-------------------------------------------------------------------------------------------+
         e  |                                                                                           |
         p  |                                                                                           |
         t  |                                                                                           |
         h  +-------------------------------------------------------------------------------------------+
                                                        Time

            +---------------------------------------+           +-------------------+-------------------+
            |                                       |           |                   |                   |
            |                                       |         y |                   |                   |
         L  |                                       |         P |                   |                   |
         a  |                                       |         a |    Platform 0     |    Platform 1     |
         t  |                                       |         r |                   |                   |
         i  |                                       |         m |                   |                   |
         t  |                                       |           |                   |                   |
         u  |                                       |           +-------------------+-------------------+
         d  |                                       |           |                   |                   |
         e  |                                       |         y |                   |                   |
            |                                       |         P |                   |                   |
            |                                       |         a |    Platform 2     |    Platform 3     |
            |                                       |         r |                   |                   |
            |                                       |         m |                   |                   |
            |                                       |           |                   |                   |
            +---------------------------------------+           +-------------------+-------------------+
                           Longitude                                    xParm               xParm

        '''
        # Nested GridSpecs for Subplots
        outer_gs = gridspec.GridSpec(2, 1, height_ratios=[1,4])
        time_gs  = gridspec.GridSpecFromSubplotSpec(1, 1, subplot_spec=outer_gs[0])
        lower_gs = gridspec.GridSpecFromSubplotSpec(1, 2, subplot_spec=outer_gs[1])
        map_gs   = gridspec.GridSpecFromSubplotSpec(1, 1, subplot_spec=lower_gs[0])
        plat1_gs = gridspec.GridSpecFromSubplotSpec(1, 1, subplot_spec=lower_gs[1])
        plat4_gs = gridspec.GridSpecFromSubplotSpec(2, 2, subplot_spec=lower_gs[1], wspace=0.0, hspace=0.0, width_ratios=[1,1], height_ratios=[1,1])

        # Get overall temporal and spatial extents of platforms requested
        allActivityStartTime, allActivityEndTime, allExtent  = self._getActivityExtent(self.args.platform)

        # Setup the time windowing and stepping - if none specified then use the entire extent that is in the database
        if self.args.hourStep:
            timeStep = timedelta(hours=self.args.hourStep)
            if self.args.hourWindow:
                timeWindow = timedelta(hours=self.args.hourWindow)
            else:
                if self.args.hourStep:
                    timeWindow = timedelta(hours=self.args.hourStep)
        else:
            timeWindow = allActivityEndTime - allActivityStartTime
            timeStep = timeWindow
        startTime = allActivityStartTime
        endTime = startTime + timeWindow

        # Get overall temporal data for placement in the temporal subplot
        platformDTHash = self._getplatformDTHash(self.args.platform)
        try:
            swrTS = self._getTimeSeriesData(allActivityStartTime, allActivityEndTime, parameterStandardName='surface_downwelling_shortwave_flux_in_air')
        except NoTSDataException, e:
            swrTS = None
            print "WARNING:", e

        # Loop through sections of the data with temporal query constraints based on the window and step command line parameters
        while endTime <= allActivityEndTime:

            # Start a new figure - size is in inches
            fig = plt.figure(figsize=(9, 6))

            # Plot temporal overview
            ax = plt.Subplot(fig, time_gs[:])
            fig.add_subplot(ax)
            if self.args.title:
                ax.set_title(self.args.title)
            self.timeSubPlot(platformDTHash, ax, allActivityStartTime, allActivityEndTime, startTime, endTime, swrTS)

            # Make scatter plots of data fromt the platforms 
            platformLineStringHash = {}
            for i, (pl, xP, yP) in enumerate(zip(self.args.platform, self.args.xParm, self.args.yParm)):
                try: 
                    if self.args.verbose: print 'Calling self._getPPData...'
                    x, y, points = self._getPPData(startTime, endTime, pl, xP, yP)
                    platformLineStringHash[pl] = LineString(points).simplify(tolerance=.001)
                except NoPPDataException, e:
                    if self.args.verbose: print e
                    continue

                if len(self.args.platform) == 1:
                    ax = plt.Subplot(fig, plat1_gs[0])
                elif len(self.args.platform) < 5:
                    ax = plt.Subplot(fig, plat4_gs[i])
                else:
                    raise Exception('Cannot handle more than 4 platform Parameter-Parameter plots')

                fig.add_subplot(ax)
                self.ppSubPlot(x, y, pl, self._getColor(pl), xP, yP, ax, startTime)

            # Plot spatial
            ax = plt.Subplot(fig, map_gs[:])
            fig.add_subplot(ax, aspect='equal')
            if self.args.verbose: print 'Calling self.spatialSubPlot()...'
            self.spatialSubPlot(platformLineStringHash, ax, allExtent)
           
            startTime = startTime + timeStep
            endTime = startTime + timeWindow

            provStr = 'Created with STOQS command ' + '\\\n'.join(wrap(self.commandline, width=100)) + ' on ' + datetime.now().ctime() + ' GMT'
            plt.figtext(0.0, 0.0, provStr, size=7, horizontalalignment='left', verticalalignment='bottom')

            fileName, wcName = self.getFilename(startTime)
            print 'Saving to file', fileName
            fig.savefig(fileName)
            plt.clf()
            plt.close()
            ##raw_input('P')

        print 'Done.'
        print  'Make an animated gif with: convert -delay 10 {wcName}.png {baseName}.gif'.format(wcName=wcName, baseName='_'.join(fileName.split('_')[:-1]))
        print  'Make an MPEG 4 with: ffmpeg -r 10 -i {baseName}.gif -vcodec mpeg4 -qscale 1 -y {baseName}.mp4'.format(baseName='_'.join(fileName.split('_')[:-1]))

    def process_command_line(self):
        '''
        The argparse library is included in Python 2.7 and is an added package for STOQS.
        '''
        import argparse
        from argparse import RawTextHelpFormatter

        examples = 'Examples:' + '\n\n' 
        examples += sys.argv[0] + " -d stoqs_september2013 -p tethys Slocum_294 dorado Slocum_260 -x bb650 optical_backscatter660nm bbp700 optical_backscatter700nm -y chlorophyll fluorescence fl700_uncorr fluorescence --plotDir /tmp --plotPrefix stoqs_september2013_ --hourStep 3 --hourWindow 6 --xLabel '' --yLabel '' --title 'Fl vs. bb (red)' --minDepth 0 --maxDepth 100\n"
        examples += sys.argv[0] + " -d stoqs_september2013_o -p tethys Slocum_294 dorado Slocum_260 -x bb650 optical_backscatter660nm bbp700 optical_backscatter700nm -y chlorophyll fluorescence fl700_uncorr fluorescence --plotDir /tmp --plotPrefix stoqs_september2013_o_ --hourStep 6 --hourWindow 12 --xLabel '' --yLabel '' --title 'Fl vs. bb (red)' --minDepth 0 --maxDepth 100\n"
        examples += sys.argv[0] + " -d stoqs_september2013_o -p dorado Slocum_294 tethys -x bbp420 optical_backscatter470nm bb470 -y fl700_uncorr fluorescence chlorophyll --plotDir /tmp --plotPrefix kraken_ --hourStep 12 --hourWindow 24 --platformColors '#ff0000' '#00ff00' '#0000ff' --xLabel '' --yLabel ''\n"
        examples += sys.argv[0] + ' -d stoqs_simz_aug2013_t -p dorado dorado dorado dorado -x bbp420 bbp700 salinity salinity -y fl700_uncorr fl700_uncorr fl700_uncorr temperature\n'
        examples += sys.argv[0] + ' -d stoqs_simz_aug2013_t -p dorado dorado dorado dorado -x bbp420 bbp700 salinity salinity -y fl700_uncorr fl700_uncorr fl700_uncorr temperature --xLabel "" --yLabel ""\n'
        examples += sys.argv[0] + ' -d stoqs_september2013_o -p dorado Slocum_294 tethys -x bbp420 optical_backscatter470nm bb470 -y fl700_uncorr fluorescence chlorophyll\n'
        examples += sys.argv[0] + ' -d stoqs_september2013_o -p dorado -x bbp420 -y fl700_uncorr\n'
        examples += sys.argv[0] + ' -d stoqs_september2013_o -p tethys -x bb470 -y chlorophyll --hourStep 12 --hourWindow 24\n'
        examples += sys.argv[0] + ' -d stoqs_september2013_o -p Slocum_294 -x optical_backscatter470nm -y fluorescence --hourStep 12 --hourWindow 24\n'
        examples += sys.argv[0] + ' -d stoqs_september2013_o -p dorado -x bbp420 -y fl700_uncorr\n'
        examples += sys.argv[0] + ' -d stoqs_march2013_o -p dorado -x bbp420 -y fl700_uncorr\n'
        examples += sys.argv[0] + ' -d stoqs_march2013_o -p daphne -x bb470 -y chlorophyll\n'
        examples += sys.argv[0] + ' -d stoqs_march2013_o -p tethys -x bb470 -y chlorophyll\n'
        examples += sys.argv[0] + ' -d stoqs_march2013_o -p tethys -x bb470 -y chlorophyll --daytime\n'
        examples += sys.argv[0] + ' -d stoqs_march2013_o -p tethys -x bb470 -y chlorophyll --nighttime\n'
        examples += '\n\nMultiple platform and parameter names are paired up in respective order.\n'
        examples += '(Image files will be written to the current working directory)'
    
        parser = argparse.ArgumentParser(formatter_class=RawTextHelpFormatter,
                                         description='Read Parameter-Parameter data from a STOQS database and make bi-plots',
                                         epilog=examples)
                                             
        parser.add_argument('-x', '--xParm', action='store', help='One or more Parameter names for the X axis', nargs='*', default='bb470', required=True)
        parser.add_argument('-y', '--yParm', action='store', help='One or more Parameter names for the Y axis', nargs='*', default='chlorophyll', required=True)
        parser.add_argument('-p', '--platform', action='store', help='One or more platform names separated by spaces', nargs='*', default='tethys', required=True)
        parser.add_argument('-d', '--database', action='store', help='Database alias', default='stoqs_september2013_o', required=True)
        parser.add_argument('--hourWindow', action='store', help='Window in hours for interval plot. If not specified it will be the same as hourStep.', type=int)
        parser.add_argument('--hourStep', action='store', help='Step though the time series and make plots at this hour interval', type=int)
        parser.add_argument('--daytime', action='store_true', help='Select only daytime hours: 10 am to 2 pm local time')
        parser.add_argument('--nighttime', action='store_true', help='Select only nighttime hours: 10 pm to 2 am local time')
        parser.add_argument('--minDepth', action='store', help='Minimum depth for data queries', default=None, type=float)
        parser.add_argument('--maxDepth', action='store', help='Maximum depth for data queries', default=None, type=float)
        parser.add_argument('--plotDir', action='store', help='Directory where to write the plot output', default='.')
        parser.add_argument('--plotPrefix', action='store', help='Prefix to use in naming plot files', default='')
        parser.add_argument('--xLabel', action='store', help='Override Parameter-Parameter X axis label - will be applied to all plots')
        parser.add_argument('--yLabel', action='store', help='Override Parameter-Parameter Y axis label - will be applied to all plots') 
        parser.add_argument('--coastlines', action='store_true', help='Draw full resolution coastlines on map - significantly increasing execution time') 
        parser.add_argument('--platformColors', action='store', help='Override database platform colors - put in quotes, e.g. "#ff0000"', nargs='*')
        parser.add_argument('--title', action='store', help='Title to appear on top of plot')
        parser.add_argument('-v', '--verbose', action='store_true', help='Turn on verbose output')
    
        self.args = parser.parse_args()
        self.commandline = ""
        for item in sys.argv:
            if item == '':
                # Preserve empty string specifications in the command line
                self.commandline += "''" + ' '
            else:
                self.commandline += item + ' '
    
    
if __name__ == '__main__':

    bp = PlatformsBiPlot()
    bp.process_command_line()
    if len(bp.args.platform) > 0:
        bp.makePlatformsBiPlots()
    else:
        bp.makePlatformsBiPlots()

