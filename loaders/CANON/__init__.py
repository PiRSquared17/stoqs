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
from SampleLoaders import SeabirdLoader, load_gulps, SubSamplesLoader 
from loaders import LoadScript
from stoqs.models import InstantPoint
from django.db.models import Max
from datetime import timedelta
import logging

def getStrideText(stride):
    '''
    Format stride into a string to be appended to the Activity name, if stride==1 return empty string
    '''
    if stride == 1:
        return ''
    else:
        return ' (stride=%d)' % stride


class CANONLoader(LoadScript):
    '''
    Common routines for loading all CANON data
    '''
    brownish = {'dorado':       '8c510a',
                'tethys':       'bf812d',
                'daphne':       'dfc27d',
                'fulmar':       'f6e8c3',
                'waveglider':   'c7eae5',
                'nps_g29':      '80cdc1',
                'l_662':        '35978f',
                'm1':           '35f78f',
                'martin':       '01665e',
                'flyer':        '11665e',
                'espdrift':     '21665e',
             }
    colors = {  'dorado':       'ffeda0',
                'other':        'ffeda0',
                'tethys':       'fed976',
                'daphne':       'feb24c',
                'makai':        'feb34c',
                'fulmar':       'fd8d3c',
                'waveglider':   'fc4e2a',
                'nps_g29':      'e31a1c',
                'l_662':        'bd0026',
                'nps29':        '0b9131',
                'nps34':        '36d40f',
                'm1':           'bd2026',
                'oa':           '0f9cd4',
                'oa2':          '2d2426',
                'hehape':       'bd2026',
                'rusalka':      'bd4026',
                'carmen':       'bd8026',
                'martin':       '800026',
                'flyer':        '801026',
                'carson':       '730a46',
                'espdrift':     '802026',
                'espmack':      '804026',
                'espbruce':     '808026',
                'Stella201':    '26f080',
                'Stella202':    'F02696',
                'Stella203':    'F08026',
                'Stella204':    'AAAA26',
                'stella203':    'F08026',
                'stella204':    'AAAA26',
                'Stella205':    '2696f0',
                'nemesis':      'FFF026',
                'ucsc294':      'FFBA26',
                'slocum_294':   'FFBA26',
                'slocum_nemesis':'FFF026',
                'ucsc260':      'FF8426',
                'slocum_260':   'FF8426',
                'wg_oa':        '0f9cd4',
                'wg_tex':       '9626ff',
             }

    def loadDorado(self, stride=None):
        '''
        Dorado specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.dorado_files], self.dorado_files):
            url = self.dorado_base + file
            DAPloaders.runDoradoLoader(url, self.campaignName, self.campaignDescription, aName, 'Dorado', self.colors['dorado'], 'auv', 'AUV mission', 
                                        self.dorado_parms, self.dbAlias, stride, grdTerrain=self.grdTerrain)
            load_gulps(aName, file, self.dbAlias)


    def loadTethys(self, stride=None):
        '''
        Tethys specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.tethys_files], self.tethys_files):
            url = self.tethys_base + file
            dataStartDatetime = None
            if self.args.append:
                # Return datetime of last timevalue - if data are loaded from multiple activities return the earliest last datetime value
                dataStartDatetime = InstantPoint.objects.using(self.dbAlias).filter(activity__name=aName).aggregate(Max('timevalue'))['timevalue__max']

            DAPloaders.runLrauvLoader(url, self.campaignName, self.campaignDescription, aName, 'Tethys', self.colors['tethys'], 'auv', 'AUV mission', 
                                        self.tethys_parms, self.dbAlias, stride, grdTerrain=self.grdTerrain, dataStartDatetime=dataStartDatetime)

    def loadDaphne(self, stride=None):
        '''
        Daphne specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.daphne_files], self.daphne_files):
            url = self.daphne_base + file
            dataStartDatetime = None
            if self.args.append:
                # Return datetime of last timevalue - if data are loaded from multiple activities return the earliest last datetime value
                dataStartDatetime = InstantPoint.objects.using(self.dbAlias).filter(activity__name=aName).aggregate(Max('timevalue'))['timevalue__max']

            # Set stride to 1 for telemetered data
            DAPloaders.runLrauvLoader(url, self.campaignName, self.campaignDescription, aName, 'Daphne', self.colors['daphne'], 'auv', 'AUV mission', 
                                        self.daphne_parms, self.dbAlias, stride, grdTerrain=self.grdTerrain, dataStartDatetime=dataStartDatetime)

    def loadMakai(self, stride=None):
        '''
        Makai specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.daphne_files], self.daphne_files):
            url = self.daphne_base + file
            dataStartDatetime = None
            if self.args.append:
                # Return datetime of last timevalue - if data are loaded from multiple activities return the earliest last datetime value
                dataStartDatetime = InstantPoint.objects.using(self.dbAlias).filter(activity__name=aName).aggregate(Max('timevalue'))['timevalue__max']

            # Set stride to 1 for telemetered data
            DAPloaders.runLrauvLoader(url, self.campaignName, self.campaignDescription, aName, 'Makai', self.colors['makai'], 'auv', 'AUV mission', 
                                        self.daphne_parms, self.dbAlias, stride, grdTerrain=self.grdTerrain, dataStartDatetime=dataStartDatetime)
    def loadMartin(self, stride=None):
        '''
        Martin specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.martin_files], self.martin_files):
            url = self.martin_base + file
            DAPloaders.runTrajectoryLoader(url, self.campaignName, self.campaignDescription, aName, 'Martin', self.colors['martin'], 'ship', 'cruise', 
                                        self.martin_parms, self.dbAlias, stride, grdTerrain=self.grdTerrain)

    def loadJMuctd(self, stride=None):
        '''
        Martin specific underway load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.JMuctd_files], self.JMuctd_files):
            url = self.JMuctd_base + file
            DAPloaders.runTrajectoryLoader(url, self.campaignName, self.campaignDescription, aName, 'John_Martin_UCTD', self.colors['martin'], 'ship', 'cruise', 
                                        self.JMuctd_parms, self.dbAlias, stride, grdTerrain=self.grdTerrain)

    def loadJMpctd(self, stride=None, platformName='John_Martin_PCTD', activitytypeName='John Martin Profile CTD Data'):
        '''
        Martin specific underway load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.JMpctd_files], self.JMpctd_files):
            url = self.JMpctd_base + file
            DAPloaders.runTrajectoryLoader(url, self.campaignName, self.campaignDescription, aName, platformName, self.colors['martin'], 'ship', activitytypeName,
                                        self.JMpctd_parms, self.dbAlias, stride, grdTerrain=self.grdTerrain)
        # load all the bottles           
        sl = SeabirdLoader(aName[:5], platformName, dbAlias=self.dbAlias, campaignName=self.campaignName, platformColor=self.colors['martin'], platformTypeName='ship', dodsBase=self.JMpctd_base)
        if self.args.verbose:
            sl.logger.setLevel(logging.DEBUG)
        sl.tdsBase= self.tdsBase
        sl.process_btl_files(self.JMpctd_files)

    def loadFulmar(self, stride=None):
        '''
        Fulmar specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.fulmar_files], self.fulmar_files):
            url = self.fulmar_base + file
            DAPloaders.runTrajectoryLoader(url, self.campaignName, self.campaignDescription, aName, 'fulmar', self.colors['fulmar'], 'ship', 'cruise', 
                                        self.fulmar_parms, self.dbAlias, stride, grdTerrain=self.grdTerrain)

    def loadNps_g29(self, stride=None):
        '''
        Glider specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.nps_g29_files], self.nps_g29_files):
            url = self.nps_g29_base + file
            print "url = %s" % url
            DAPloaders.runGliderLoader(url, self.campaignName, self.campaignDescription, aName, 'nps_g29', self.colors['nps_g29'], 'glider', 'Glider Mission', 
                                        self.nps_g29_parms, self.dbAlias, stride, grdTerrain=self.grdTerrain)

    def loadL_662(self, stride=None):
        '''
        Glider specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.l_662_files], self.l_662_files):
            url = self.l_662_base + file
            print "url = %s" % url
            DAPloaders.runGliderLoader(url, self.campaignName, self.campaignDescription, aName, 'SPRAY_Glider', self.colors['l_662'], 'glider', 'Glider Mission', 
                                        self.l_662_parms, self.dbAlias, stride, self.l_662_startDatetime, self.l_662_endDatetime, grdTerrain=self.grdTerrain)

    def load_NPS29(self, stride=None):
        '''
        Glider specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.nps29_files], self.nps29_files):
            url = self.nps29_base + file

            dataStartDatetime = None
            if self.args.append:
                # Return datetime of last timevalue - if data are loaded from multiple activities return the earliest last datetime value
                dataStartDatetime = InstantPoint.objects.using(self.dbAlias).filter(activity__name=aName).aggregate(Max('timevalue'))['timevalue__max']

            DAPloaders.runGliderLoader(url, self.campaignName, self.campaignDescription, aName, 'NPS_Glider_29', self.colors['nps29'], 'glider', 'Glider Mission', 
                                        self.nps29_parms, self.dbAlias, stride, self.nps29_startDatetime, self.nps29_endDatetime, grdTerrain=self.grdTerrain, 
                                        dataStartDatetime=dataStartDatetime)

    def load_NPS34(self, stride=None):
        '''
        Glider specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.nps34_files], self.nps34_files):
            url = self.nps34_base + file
            print "url = %s" % url
            DAPloaders.runGliderLoader(url, self.campaignName, self.campaignDescription, aName, 'NPS_Glider_34', self.colors['nps34'], 'glider', 'Glider Mission', 
                                        self.nps34_parms, self.dbAlias, stride, self.nps34_startDatetime, self.nps34_endDatetime, grdTerrain=self.grdTerrain)

    def load_glider_ctd(self, stride=None):
        '''
        Glider load functions.  Requires apriori knowledge of glider file names so we can extract platform and color name
        To be used with gliders that follow the same naming convention, i.e. nemesis_ctd.nc, ucsc260_ctd.nc
        and that load the exact same parameters, i.e. TEMP, PSAL or TEMP, PSAL, FLU2 or TEMP, FLU2, OPBS etc
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.glider_ctd_files], self.glider_ctd_files):
            url = self.glider_ctd_base + file
            gplatform=aName.split('_')[0].upper() + '_Glider'
            gname=aName.split('_')[0].lower()
            print "url = %s" % url
            print "platform = %s" % gplatform 
            DAPloaders.runGliderLoader(url, self.campaignName, self.campaignDescription, aName, gplatform, self.colors[gname], 'glider', 'Glider Mission', 
                                        self.glider_ctd_parms, self.dbAlias, stride, self.glider_ctd_startDatetime, self.glider_ctd_endDatetime, grdTerrain=self.grdTerrain)

    def load_glider_met(self, stride=None):
        '''
        Glider load functions.  Requires apriori knowledge of glider file names so we can extract platform and color name
        To be used with gliders that follow the same naming convention, i.e. nemesis_met.nc, ucsc260_met.nc
        and that load the exact same parameters, i.e. meanu,meanv or windspeed, winddirection etc.
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.glider_met_files], self.glider_met_files):
            url = self.glider_met_base + file
            gplatform=aName.split('_')[0].upper() + '_Glider'
            gname=aName.split('_')[0].lower()
            print "url = %s" % url
            print "platform = %s" % gplatform 
            DAPloaders.runGliderLoader(url, self.campaignName, self.campaignDescription, aName, gplatform, self.colors[gname], 'glider', 'Glider Mission', 
                                        self.glider_met_parms, self.dbAlias, stride, self.glider_met_startDatetime, self.glider_met_endDatetime, grdTerrain=self.grdTerrain)


    def load_slocum_260(self, stride=None):
        '''
        Glider specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.slocum_260_files], self.slocum_260_files):
            url = self.slocum_260_base + file
            print "url = %s" % url
            DAPloaders.runGliderLoader(url, self.campaignName, self.campaignDescription, aName, 'Slocum_260', self.colors['slocum_260'], 'glider', 'Glider Mission', 
                                        self.slocum_260_parms, self.dbAlias, stride, self.slocum_260_startDatetime, self.slocum_260_endDatetime, grdTerrain=self.grdTerrain)

    def load_slocum_294(self, stride=None):
        '''
        Glider specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.slocum_294_files], self.slocum_294_files):
            url = self.slocum_294_base + file
            print "url = %s" % url
            DAPloaders.runGliderLoader(url, self.campaignName, self.campaignDescription, aName, 'Slocum_294', self.colors['slocum_294'], 'glider', 'Glider Mission', 
                                        self.slocum_294_parms, self.dbAlias, stride, self.slocum_294_startDatetime, self.slocum_294_endDatetime,
                                        grdTerrain=self.grdTerrain)

    def load_slocum_nemesis(self, stride=None):
        '''
        Glider specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.slocum_nemesis_files], self.slocum_nemesis_files):
            url = self.slocum_nemesis_base + file
            print "url = %s" % url
            DAPloaders.runGliderLoader(url, self.campaignName, self.campaignDescription, aName, 'Slocum_nemesis', self.colors['slocum_nemesis'], 'glider', 'Glider Mission', 
                                        self.slocum_nemesis_parms, self.dbAlias, stride, self.slocum_nemesis_startDatetime, self.slocum_nemesis_endDatetime,
                                        grdTerrain=self.grdTerrain)

    def load_wg_oa_pco2(self, stride=None):
        '''
        Glider specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.wg_oa_pco2_files], self.wg_oa_pco2_files):
            url = self.wg_oa_pco2_base + file
            print "url = %s" % url
            DAPloaders.runGliderLoader(url, self.campaignName, self.campaignDescription, aName, 'OA_Glider', self.colors['wg_oa'], 'waveglider', 'Glider Mission', 
                                        self.wg_oa_pco2_parms, self.dbAlias, stride, self.wg_oa_pco2_startDatetime, self.wg_oa_pco2_endDatetime,
                                        grdTerrain=self.grdTerrain)

    def load_wg_oa_ctd(self, stride=None):
        '''
        Glider specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.wg_oa_ctd_files], self.wg_oa_ctd_files):
            url = self.wg_oa_ctd_base + file
            print "url = %s" % url
            DAPloaders.runGliderLoader(url, self.campaignName, self.campaignDescription, aName, 'OA_Glider', self.colors['wg_oa'], 'waveglider', 'Glider Mission', 
                                        self.wg_oa_ctd_parms, self.dbAlias, stride, self.wg_oa_ctd_startDatetime, self.wg_oa_ctd_endDatetime,
                                        grdTerrain=self.grdTerrain)

    def load_wg_tex_ctd(self, stride=None):
        '''
        Glider specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.wg_tex_ctd_files], self.wg_tex_ctd_files):
            url = self.wg_tex_ctd_base + file
            print "url = %s" % url
            DAPloaders.runGliderLoader(url, self.campaignName, self.campaignDescription, aName, 'Tex_Glider', self.colors['wg_tex'], 'waveglider', 'Glider Mission', 
                                        self.wg_tex_ctd_parms, self.dbAlias, stride, self.wg_tex_ctd_startDatetime, self.wg_tex_ctd_endDatetime,
                                        grdTerrain=self.grdTerrain)

    def load_wg_oa_met(self, stride=None):
        '''
        Glider specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.wg_oa_met_files], self.wg_oa_met_files):
            url = self.wg_oa_met_base + file
            print "url = %s" % url
            DAPloaders.runGliderLoader(url, self.campaignName, self.campaignDescription, aName, 'OA_Glider', self.colors['wg_oa'], 'waveglider', 'Glider Mission', 
                                        self.wg_oa_met_parms, self.dbAlias, stride, self.wg_oa_met_startDatetime, self.wg_oa_met_endDatetime,
                                        grdTerrain=self.grdTerrain)

    def load_wg_tex_met(self, stride=None):
        '''
        Glider specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.wg_tex_met_files], self.wg_tex_met_files):
            url = self.wg_tex_met_base + file
            print "url = %s" % url
            DAPloaders.runGliderLoader(url, self.campaignName, self.campaignDescription, aName, 'Tex_Glider', self.colors['wg_tex'], 'waveglider', 'Glider Mission', 
                                        self.wg_tex_met_parms, self.dbAlias, stride, self.wg_tex_met_startDatetime, self.wg_tex_met_endDatetime,
                                        grdTerrain=self.grdTerrain)

    def load_wg_tex(self, stride=None):
        '''
        Glider specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.wg_tex_files], self.wg_tex_files):
            url = self.wg_tex_base + file
            print "url = %s" % url
            DAPloaders.runGliderLoader(url, self.campaignName, self.campaignDescription, aName, 'Tex_Glider', self.colors['wg_tex'], 'waveglider', 'Glider Mission', 
                                        self.wg_tex_parms, self.dbAlias, stride, self.wg_tex_startDatetime, self.wg_tex_endDatetime,
                                        grdTerrain=self.grdTerrain)

    def load_wg_oa(self, stride=None):
        '''
        Glider specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.wg_oa_files], self.wg_oa_files):
            url = self.wg_oa_base + file
            print "url = %s" % url
            DAPloaders.runGliderLoader(url, self.campaignName, self.campaignDescription, aName, 'OA_Glider', self.colors['wg_oa'], 'waveglider', 'Glider Mission', 
                                        self.wg_oa_parms, self.dbAlias, stride, self.wg_oa_startDatetime, self.wg_oa_endDatetime,
                                        grdTerrain=self.grdTerrain)

    def loadOA1pco2(self, stride=None):
        '''
        Mooring OA specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.OA1pco2_files], self.OA1pco2_files):
            url = os.path.join(self.OA1pco2_base, file)
            print "url = %s" % url
            DAPloaders.runMooringLoader(url, self.campaignName, self.campaignDescription, aName, 'OA1_Mooring', self.colors['oa'], 'mooring', 'Mooring Deployment', 
                                        self.OA1pco2_parms, self.dbAlias, stride, self.OA1pco2_startDatetime, self.OA1pco2_endDatetime)


    def loadOA1fl(self, stride=None):
        '''
        Mooring OA specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.OA1fl_files], self.OA1fl_files):
            url = os.path.join(self.OA1fl_base, file)
            print "url = %s" % url
            DAPloaders.runMooringLoader(url, self.campaignName, self.campaignDescription, aName, 'OA1_Mooring', self.colors['oa'], 'mooring', 'Mooring Deployment', 
                                        self.OA1fl_parms, self.dbAlias, stride, self.OA1fl_startDatetime, self.OA1fl_endDatetime)


    def loadOA1o2(self, stride=None):
        '''
        Mooring OA specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.OA1o2_files], self.OA1o2_files):
            url = os.path.join(self.OA1o2_base, file)
            print "url = %s" % url
            DAPloaders.runMooringLoader(url, self.campaignName, self.campaignDescription, aName, 'OA1_Mooring', self.colors['oa'], 'mooring', 'Mooring Deployment', 
                                        self.OA1o2_parms, self.dbAlias, stride, self.OA1o2_startDatetime, self.OA1o2_endDatetime)

    def loadOA1ctd(self, stride=None):
        '''
        Mooring OA specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.OA1ctd_files], self.OA1ctd_files):
            url = os.path.join(self.OA1ctd_base, file)
            print "url = %s" % url
            DAPloaders.runMooringLoader(url, self.campaignName, self.campaignDescription, aName, 'OA1_Mooring', self.colors['oa'], 'mooring', 'Mooring Deployment', 
                                        self.OA1ctd_parms, self.dbAlias, stride, self.OA1ctd_startDatetime, self.OA1ctd_endDatetime)


    def loadOA1pH(self, stride=None):
        '''
        Mooring OA specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.OA1pH_files], self.OA1pH_files):
            url = os.path.join(self.OA1pH_base, file)
            print "url = %s" % url
            DAPloaders.runMooringLoader(url, self.campaignName, self.campaignDescription, aName, 'OA1_Mooring', self.colors['oa'], 'mooring', 'Mooring Deployment', 
                                        self.OA1pH_parms, self.dbAlias, stride, self.OA1pH_startDatetime, self.OA1pH_endDatetime)


    def loadOA1met(self, stride=None):
        '''
        Mooring OA specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.OA1met_files], self.OA1met_files):
            url = os.path.join(self.OA1met_base, file)
            print "url = %s" % url
            DAPloaders.runMooringLoader(url, self.campaignName, self.campaignDescription, aName, 'OA1_Mooring', self.colors['oa'], 'mooring', 'Mooring Deployment', 
                                        self.OA1met_parms, self.dbAlias, stride, self.OA1met_startDatetime, self.OA1met_endDatetime)


    def loadOA2pco2(self, stride=None):
        '''
        Mooring OA specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.OA2pco2_files], self.OA2pco2_files):
            url = os.path.join(self.OA2pco2_base, file)
            print "url = %s" % url
            DAPloaders.runMooringLoader(url, self.campaignName, self.campaignDescription, aName, 'OA2_Mooring', self.colors['oa2'], 'mooring', 'Mooring Deployment', 
                                        self.OA2pco2_parms, self.dbAlias, stride, self.OA2pco2_startDatetime, self.OA2pco2_endDatetime)


    def loadOA2fl(self, stride=None):
        '''
        Mooring OA specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.OA2fl_files], self.OA2fl_files):
            url = os.path.join(self.OA2fl_base, file)
            print "url = %s" % url
            DAPloaders.runMooringLoader(url, self.campaignName, self.campaignDescription, aName, 'OA2_Mooring', self.colors['oa2'], 'mooring', 'Mooring Deployment', 
                                        self.OA2fl_parms, self.dbAlias, stride, self.OA2fl_startDatetime, self.OA2fl_endDatetime)


    def loadOA2o2(self, stride=None):
        '''
        Mooring OA specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.OA2o2_files], self.OA2o2_files):
            url = os.path.join(self.OA2o2_base, file)
            print "url = %s" % url
            DAPloaders.runMooringLoader(url, self.campaignName, self.campaignDescription, aName, 'OA2_Mooring', self.colors['oa2'], 'mooring', 'Mooring Deployment', 
                                        self.OA2o2_parms, self.dbAlias, stride, self.OA2o2_startDatetime, self.OA2o2_endDatetime)

    def loadOA2ctd(self, stride=None):
        '''
        Mooring OA specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.OA2ctd_files], self.OA2ctd_files):
            url = os.path.join(self.OA2ctd_base, file)
            print "url = %s" % url
            DAPloaders.runMooringLoader(url, self.campaignName, self.campaignDescription, aName, 'OA2_Mooring', self.colors['oa2'], 'mooring', 'Mooring Deployment', 
                                        self.OA2ctd_parms, self.dbAlias, stride, self.OA2ctd_startDatetime, self.OA2ctd_endDatetime)


    def loadOA2pH(self, stride=None):
        '''
        Mooring OA specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.OA2pH_files], self.OA2pH_files):
            url = os.path.join(self.OA2pH_base, file)
            print "url = %s" % url
            DAPloaders.runMooringLoader(url, self.campaignName, self.campaignDescription, aName, 'OA2_Mooring', self.colors['oa2'], 'mooring', 'Mooring Deployment', 
                                        self.OA2pH_parms, self.dbAlias, stride, self.OA2pH_startDatetime, self.OA2pH_endDatetime)


    def loadOA2met(self, stride=None):
        '''
        Mooring OA specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.OA2met_files], self.OA2met_files):
            url = os.path.join(self.OA2met_base, file)
            print "url = %s" % url
            DAPloaders.runMooringLoader(url, self.campaignName, self.campaignDescription, aName, 'OA2_Mooring', self.colors['oa2'], 'mooring', 'Mooring Deployment', 
                                        self.OA2met_parms, self.dbAlias, stride, self.OA2met_startDatetime, self.OA2met_endDatetime)

    def loadBruceMoor(self, stride=None):
        '''
        Mooring Bruce specific load functions
        '''
        stride = stride or self.stride
        pName = 'ESP_Bruce_Mooring'
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.bruce_moor_files], self.bruce_moor_files):
            url = os.path.join(self.bruce_moor_base, file)
            print "url = %s" % url
            DAPloaders.runMooringLoader(url, self.campaignName, self.campaignDescription, aName, pName, self.colors['espbruce'], 'mooring', 
                    'Mooring Deployment', self.bruce_moor_parms, self.dbAlias, stride, self.bruce_moor_startDatetime, self.bruce_moor_endDatetime)

        # Let browser code use {{STATIC_URL}} to fill in the /stoqs/static path
        self.addPlatformResources('x3d/ESPMooring/esp_base_scene.x3d', pName)

    def loadMackMoor(self, stride=None):
        '''
        Mooring Mack specific load functions
        '''
        stride = stride or self.stride
        pName = 'ESP_Mack_Mooring'
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.mack_moor_files], self.mack_moor_files):
            url = os.path.join(self.mack_moor_base, file)
            print "url = %s" % url
            DAPloaders.runMooringLoader(url, self.campaignName, self.campaignDescription, aName, pName, self.colors['espmack'], 'mooring', 'Mooring Deployment',                                       self.mack_moor_parms, self.dbAlias, stride, self.mack_moor_startDatetime, self.mack_moor_endDatetime)

        # Let browser code use {{STATIC_URL}} to fill in the /stoqs/static path
        self.addPlatformResources('x3d/ESPMooring/esp_base_scene.x3d', pName)

    def loadM1(self, stride=None):
        '''
        Mooring M1 specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.m1_files], self.m1_files):
            url = os.path.join(self.m1_base, file)
            
            dataStartDatetime = None
            if self.args.append:
                # Return datetime of last timevalue - if data are loaded from multiple activities return the earliest last datetime value
                dataStartDatetime = InstantPoint.objects.using(self.dbAlias).filter(activity__name=aName).aggregate(Max('timevalue'))['timevalue__max']
                if dataStartDatetime:
                    # Subract an hour to fill in missing_values at end from previous load
                    dataStartDatetime = dataStartDatetime - timedelta(seconds=3600)

            DAPloaders.runMooringLoader(url, self.campaignName, self.campaignDescription, aName, 'M1_Mooring', self.colors['m1'], 'mooring', 'Mooring Deployment', 
                                        self.m1_parms, self.dbAlias, stride, self.m1_startDatetime, self.m1_endDatetime, dataStartDatetime)

    def loadM1ts(self, stride=None):
        '''
        Mooring M1ts specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.m1ts_files], self.m1ts_files):
            url = self.m1ts_base + file
            print "url = %s" % url
            DAPloaders.runMooringLoader(url, self.campaignName, self.campaignDescription, aName, 'M1_Mooring', self.colors['m1'], 'mooring', 'Mooring Deployment', 
                                        self.m1ts_parms, self.dbAlias, stride, self.m1ts_startDatetime, self.m1ts_endDatetime)

    def loadM1met(self, stride=None):
        '''
        Mooring M1met specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.m1met_files], self.m1met_files):
            url = self.m1met_base + file
            print "url = %s" % url
            DAPloaders.runMooringLoader(url, self.campaignName, self.campaignDescription, aName, 'M1_Mooring', self.colors['m1'], 'mooring', 'Mooring Deployment', 
                                        self.m1met_parms, self.dbAlias, stride, self.m1met_startDatetime, self.m1met_endDatetime)

    def loadHeHaPe(self, stride=None):
        '''
        Glider specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.hehape_files], self.hehape_files):
            url = self.hehape_base + file
            print "url = %s" % url
            DAPloaders.runGliderLoader(url, self.campaignName, self.campaignDescription, aName, 'hehape', self.colors['hehape'], 'glider', 'Glider Mission', 
                                        self.hehape_parms, self.dbAlias, stride, grdTerrain=self.grdTerrain)

    def loadRusalka(self, stride=None):
        '''
        Glider specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.rusalka_files], self.rusalka_files):
            url = self.rusalka_base + file
            print "url = %s" % url
            DAPloaders.runGliderLoader(url, self.campaignName, self.campaignDescription, aName, 'rusalka', self.colors['rusalka'], 'glider', 'Glider Mission', 
                                        self.rusalka_parms, self.dbAlias, stride, grdTerrain=self.grdTerrain)

    def loadCarmen(self, stride=None):
        '''
        Glider specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.carmen_files], self.carmen_files):
            url = self.carmen_base + file
            print "url = %s" % url
            DAPloaders.runGliderLoader(url, self.campaignName, self.campaignDescription, aName, 'carmen', self.colors['carmen'], 'glider', 'Glider Mission', 
                                        self.carmen_parms, self.dbAlias, stride, grdTerrain=self.grdTerrain)

    def loadWaveglider(self, stride=None):
        '''
        Glider specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.waveglider_files], self.waveglider_files):
            url = self.waveglider_base + file
            print "url = %s" % url
            DAPloaders.runGliderLoader(url, self.campaignName, self.campaignDescription, aName, 'waveglider', self.colors['waveglider'], 'glider', 'Glider Mission', 
                                        self.waveglider_parms, self.dbAlias, stride, self.waveglider_startDatetime, self.waveglider_endDatetime,
                                        grdTerrain=self.grdTerrain)

    def loadStella(self, stride=None):
        '''
        Stella drift specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.stella_files], self.stella_files):
            url = self.stella_base + file
            print "url = %s" % url
            dname='Stella' + aName[6:9]
            DAPloaders.runTrajectoryLoader(url, self.campaignName, self.campaignDescription, aName, dname, self.colors[dname], 'drifter', 'Stella drifter Mission', 
                                        self.stella_parms, self.dbAlias, stride, grdTerrain=self.grdTerrain)

    def loadESPdrift(self, stride=None):
        '''
        ESPdrift specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.espdrift_files], self.espdrift_files):
            url = self.espdrift_base + file
            print "url = %s" % url
            DAPloaders.runTrajectoryLoader(url, self.campaignName, self.campaignDescription, aName, 'espdrift', self.colors['espdrift'], 'drifter', 'ESP drift Mission', 
                                        self.espdrift_parms, self.dbAlias, stride, grdTerrain=self.grdTerrain)

    def loadESPmack(self, stride=None):
        '''
        ESPmack specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.espmack_files], self.espmack_files):
            url = self.espmack_base + file
            print "url = %s" % url
            DAPloaders.runTrajectoryLoader(url, self.campaignName, self.campaignDescription, aName, 'ESP_Mack_Drifter', self.colors['espmack'], 'espmack', 'ESP mack Mission', 
                                        self.espmack_parms, self.dbAlias, stride, grdTerrain=self.grdTerrain)

    def loadESPbruce(self, stride=None):
        '''
        ESPbruce specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.espbruce_files], self.espbruce_files):
            url = self.espbruce_base + file
            print "url = %s" % url
            DAPloaders.runTrajectoryLoader(url, self.campaignName, self.campaignDescription, aName, 'espbruce', self.colors['espbruce'], 'espbruce', 'ESP bruce Mission', 
                                        self.espbruce_parms, self.dbAlias, stride, grdTerrain=self.grdTerrain)

    def loadWFuctd(self, stride=None, platformName='WesternFlyer_UCTD', activitytypeName='Western Flyer Underway CTD Data'):
        '''
        WF uctd specific load functions.  Override defaults for @platformName and activitytypeName if it's desired
        to consider uctd and pctd coming from the same platform.  You may want to do this to use the data 
        visualization capabilities in STOQS.
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.wfuctd_files], self.wfuctd_files):
            url = self.wfuctd_base + file
            print "url = %s" % url
            DAPloaders.runTrajectoryLoader(url, self.campaignName, self.campaignDescription, aName, platformName, self.colors['flyer'], 'ship', activitytypeName,
                                        self.wfuctd_parms, self.dbAlias, stride, grdTerrain=self.grdTerrain)

    def loadWFpctd(self, stride=None, platformName='WesternFlyer_PCTD', activitytypeName='Western Flyer Profile CTD Data'):
        '''
        WF pctd specific load functions. Override defaults for @platformName and activitytypeName if it's desired
        to consider uctd and pctd coming from the same platform.  You may want to do this to use the data 
        visualization capabilities in STOQS.
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a.split('.')[0] + getStrideText(stride) for a in self.wfpctd_files], self.wfpctd_files):
            url = self.wfpctd_base + file
            print "url = %s" % url
            DAPloaders.runTrajectoryLoader(url, self.campaignName, self.campaignDescription, aName, platformName, self.colors['flyer'], 'ship', activitytypeName, 
                                        self.wfpctd_parms, self.dbAlias, stride, grdTerrain=self.grdTerrain)
        # Now load all the bottles           
        sl = SeabirdLoader('activity name', platformName, dbAlias=self.dbAlias, campaignName=self.campaignName, platformColor=self.colors['flyer'], dodsBase=self.wfpctd_base)
        if self.args.verbose:
            sl.logger.setLevel(logging.DEBUG)
        sl.tdsBase= self.tdsBase
        sl.process_btl_files(self.wfpctd_files)

    def loadRCuctd(self, stride=None, platformName='RachelCarson_UCTD', activitytypeName='Rachel Carson Underway CTD Data'):
        '''
        RC uctd specific load functions
        '''
        stride = stride or self.stride
        for (aName, file) in zip([ a + getStrideText(stride) for a in self.rcuctd_files], self.rcuctd_files):
            url = self.rcuctd_base + file
            print "url = %s" % url
            DAPloaders.runTrajectoryLoader(url, self.campaignName, self.campaignDescription, aName, platformName, self.colors['carson'], 'ship', activitytypeName, 
                                        self.rcuctd_parms, self.dbAlias, stride, grdTerrain=self.grdTerrain)

    def loadRCpctd(self, stride=None, platformName='RachelCarson_PCTD', activitytypeName='Rachel Carson Profile CTD Data'):
        '''
        RC pctd specific load functions
        '''
        stride = stride or self.stride
        #platformName = 'rc_pctd'
        for (aName, file) in zip([ a.split('.')[0] + getStrideText(stride) for a in self.rcpctd_files], self.rcpctd_files):
            url = self.rcpctd_base + file
            print "url = %s" % url
            DAPloaders.runTrajectoryLoader(url, self.campaignName, self.campaignDescription, aName, platformName, self.colors['carson'], 'ship', activitytypeName, 
                                        self.rcpctd_parms, self.dbAlias, stride, grdTerrain=self.grdTerrain)
        # load all the bottles           

        sl = SeabirdLoader(aName[:5], platformName, dbAlias=self.dbAlias, campaignName=self.campaignName, platformColor=self.colors['carson'], platformTypeName='ship', dodsBase=self.rcpctd_base)
        if self.args.verbose:
            sl.logger.setLevel(logging.DEBUG)
        sl.tdsBase= self.tdsBase
        sl.process_btl_files(self.rcpctd_files)

    def loadSubSamples(self):
        '''
        Load water sample analysis Sampled data values from spreadsheets (.csv files).  Expects to have the subsample_csv_base and
        subsample_csv_files set by the load script.
        '''
        ssl = SubSamplesLoader('', '', dbAlias=self.dbAlias)
        if self.args.verbose:
            ssl.logger.setLevel(logging.DEBUG)
        for csvFile in [ os.path.join(self.subsample_csv_base, f) for f in self.subsample_csv_files ]:
            print "Processing subsamples from file", csvFile
            ssl.process_subsample_file(csvFile, False)

    def loadAll(self, stride=None):
        '''
        Execute all the load functions - this method is being deprecated as optimal strides vary for each platform
        '''
        stride = stride or self.stride
        loaders = [ 'loadDorado', 'loadTethys', 'loadDaphne', 'loadMartin', 'loadFulmar', 'loadNps_g29', 'loadWaveglider', 'loadL_662', 'loadESPdrift',
                    'loadWFuctd', 'loadWFpctd']
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
    # Instance variable settings
    cl = CANONLoader('default', 'Test Load')
    cl.stride = 1000
    cl.dorado_base = 'http://dods.mbari.org/opendap/data/auvctd/surveys/2010/netcdf/'
    cl.dorado_files = ['Dorado389_2010_300_00_300_00_decim.nc']

    # Execute the load
    cl.process_command_line()

    cl.loadAll()



