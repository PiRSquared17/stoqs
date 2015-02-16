#!/usr/bin/env python

__author__ = "Mike McCann"
__copyright__ = "Copyright 2015, MBARI"
__license__ = "GPL"
__maintainer__ = "Mike McCann"
__email__ = "mccann at mbari.org"
__status__ = "Development"
__doc__ = '''

Script to transfer information between biom-format files and a STOQS database.
Requires Python 2.7

Mike McCann
MBARI 1 February 2015

@var __date__: Date of last svn commit
@undocumented: __doc__ parser
@author: __author__
@status: __status__
@license: __license__
'''

import os
import sys
os.environ['DJANGO_SETTINGS_MODULE']='settings'
project_dir = os.path.join(os.path.dirname(__file__), "../")
sys.path.insert(0, project_dir)

import csv
import logging
from biom.table import Table

class BiomSTOQS():
    '''Data and methods to support data transfers
    '''

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    def add_metadata_from_stoqs(self):
        '''Look for data matching samples from biomFile in the specified STOQS
        database and add to the biom-format file.
        '''
        pass

                                    

    def process_command_line(self):
        '''The argparse library is included in Python 2.7 and is an added package for STOQS.
        '''
        import argparse
        from argparse import RawTextHelpFormatter

        examples = 'Examples:' + '\n\n' 
        examples += "  Add metadata to Samples axis of biom-format file:\n"
        examples += "    " + sys.argv[0] + " --database stoqs_simz_aug2013_t"
        examples += " --addMetadataFromSTOQS "
        examples += " --biomFile otu_table_newsier_90nounclass.biom\n"
        examples += "\n"
        examples += '\nIf running from cde-package replace ".py" with ".py.cde".'
    
        parser = argparse.ArgumentParser(formatter_class=RawTextHelpFormatter,
                                         description='Script to load parent Samples for Tow Net data',
                                         epilog=examples)
                                             
        parser.add_argument('-d', '--database', action='store', help='Database alias', required=True)

        parser.add_argument('--addMetadataFromSTOQS', action='store_true', help='Add relevant STOQS metadata attributes to biomFile')
        parser.add_argument('--biolFile', action='store', help='Name of biom-format file')

        parser.add_argument('-v', '--verbose', nargs='?', choices=[1,2,3], type=int, help='Turn on verbose output. Higher number = more output.', const=1)
    
        self.args = parser.parse_args()
        self.commandline = ' '.join(sys.argv)

        if self.args.verbose > 1:
            self.logger.setLevel(logging.DEBUG)
        elif self.args.verbose >0:
            self.logger.setLevel(logging.INFO)
    
if __name__ == '__main__':

    bs = BiomSTOQS()
    bs.process_command_line()

    if bs.args.addMetadataFromSTOQS:
        bs.add_metadata_from_stoqs()


