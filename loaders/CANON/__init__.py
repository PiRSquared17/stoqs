#!/usr/bin/env python
__author__    = 'Mike McCann'
__copyright__ = '2011'
__license__   = 'GPL v3'
__contact__   = 'mccann at mbari.org'

__doc__ = '''

Contains class for common routines for loading all CANON data

Mike McCann
MBARI 22 April 2012

@undocumented: __doc__ parser
@status: production
@license: GPL
'''

import os
import sys
os.environ['DJANGO_SETTINGS_MODULE']='settings'
project_dir = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../"))  # settings.py is one dir up


import DAPloaders
import GulperLoader


class CANONLoader(object):
    '''
    Common routines for loading all CANON data
    '''
    stride = 1
    brownish = {'dorado':       '8c510a',
                'tethys':       'bf812d',
                'daphne':       'dfc27d',
                'fulmar':       'f6e8c3',
                'waveglider':   'c7eae5',
                'nps_g29':      '80cdc1',
                'l_662':        '35978f',
                'martin':       '01665e',
             }
    colors = {  'dorado':       'ffeda0',
                'tethys':       'fed976',
                'daphne':       'feb24c',
                'fulmar':       'fd8d3c',
                'waveglider':   'fc4e2a',
                'nps_g29':      'e31a1c',
                'l_662':        '8d0026',
                'martin':       '800026',
             }

    def __init__(self, dbAlias, campaignName):
        self.dbAlias = dbAlias
        self.campaignName = campaignName


    def loadDorado(self):
        '''
        Dorado specific load functions
        '''
        for (aName, file) in zip([ a + ' (stride=%d)' % self.stride for a in self.dorado_files], self.dorado_files):
            url = self.dorado_base + file
            DAPloaders.runDoradoLoader(url, self.campaignName, aName, 'dorado', self.colors['dorado'], 'auv', 'AUV mission', 
                                        self.dbAlias, self.stride)
            GulperLoader.load_gulps(aName, file, self.dbAlias)


    def loadTethys(self):
        '''
        Tethys specific load functions
        '''
        for (aName, file) in zip([ a + ' (stride=%d)' % self.stride for a in self.tethys_files], self.tethys_files):
            url = self.tethys_base + file
            DAPloaders.runLrauvLoader(url, self.campaignName, aName, 'tethys', self.colors['tethys'], 'auv', 'AUV mission', 
                                        self.tethys_parms, self.dbAlias, self.stride)

    def loadDaphne(self):
        '''
        Daphne specific load functions
        '''
        for (aName, file) in zip([ a + ' (stride=%d)' % self.stride for a in self.daphne_files], self.daphne_files):
            url = self.daphne_base + file
            DAPloaders.runLrauvLoader(url, self.campaignName, aName, 'daphne', self.colors['daphne'], 'auv', 'AUV mission', 
                                        self.daphne_parms, self.dbAlias, self.stride)

    def loadMartin(self):
        '''
        Martin specific load functions
        '''
        for (aName, file) in zip([ a + ' (stride=%d)' % self.stride for a in self.martin_files], self.martin_files):
            url = self.martin_base + file
            DAPloaders.runTrajectoryLoader(url, self.campaignName, aName, 'martin', self.colors['martin'], 'ship', 'cruise', 
                                        self.martin_parms, self.dbAlias, self.stride)

    def loadFulmar(self):
        '''
        Fulmar specific load functions
        '''
        for (aName, file) in zip([ a + ' (stride=%d)' % self.stride for a in self.fulmar_files], self.fulmar_files):
            url = self.fulmar_base + file
            DAPloaders.runTrajectoryLoader(url, self.campaignName, aName, 'fulmar', self.colors['fulmar'], 'ship', 'cruise', 
                                        self.fulmar_parms, self.dbAlias, self.stride)

    def loadNps_g29(self):
        '''
        Glider specific load functions
        '''
        for (aName, file) in zip([ a + ' (stride=%d)' % self.stride for a in self.nps_g29_files], self.nps_g29_files):
            url = self.nps_g29_base + file
            print "url = %s" % url
            DAPloaders.runGliderLoader(url, self.campaignName, aName, 'nps_g29', self.colors['nps_g29'], 'glider', 'Glider Mission', 
                                        self.nps_g29_parms, self.dbAlias, self.stride)

    def loadL_662(self):
        '''
        Glider specific load functions
        '''
        for (aName, file) in zip([ a + ' (stride=%d)' % self.stride for a in self.l_662_files], self.l_662_files):
            url = self.l_662_base + file
            print "url = %s" % url
            DAPloaders.runGliderLoader(url, self.campaignName, aName, 'l_662', self.colors['l_662'], 'glider', 'Glider Mission', 
                                        self.nps_g29_parms, self.dbAlias, self.stride)

    def loadWaveglider(self):
        '''
        Glider specific load functions
        '''
        for (aName, file) in zip([ a + ' (stride=%d)' % self.stride for a in self.waveglider_files], self.waveglider_files):
            url = self.waveglider_base + file
            print "url = %s" % url
            DAPloaders.runGliderLoader(url, self.campaignName, aName, 'waveglider', self.colors['waveglider'], 'glider', 'Glider Mission', 
                                        self.waveglider_parms, self.dbAlias, self.stride)

    def loadAll(self):
        '''
        Execute all the load functions
        '''
        ##loaders = ['loadDorado', 'loadTethys', 'loadDaphne', 'loadMartin', 'loadFulmar', 'loadNps_g29', 'loadWaveglider']
        loaders = ['loadDorado', 'loadTethys', 'loadDaphne', 'loadMartin', 'loadFulmar', 'loadWaveglider']
        for loader in loaders:
            if hasattr(self, loader):
                # Call the loader if it exists
                try:
                    getattr(self, loader)()
                except AttributeError as e:
                    print e
                    print "WARNING: No data from %s for dbAlias = %s, campaignName = %s" % (loader, self.dbAlias, self.campaignName)
                    pass


if __name__ == '__main__':
    '''
    Test operation of this class
    '''
    cl = CANONLoader('default', 'Test Load')
    cl.stride = 1000
    cl.dorado_base = 'http://dods.mbari.org/opendap/data/auvctd/surveys/2010/netcdf/'
    cl.dorado_files = ['Dorado389_2010_300_00_300_00_decim.nc']
    cl.loadAll()


