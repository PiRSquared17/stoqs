# A collection of various utility functions
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# An epoch good for time axis labels - OceanSITES uses 1 Jan 1950
EPOCH_STRING = '1950-01-01'
EPOCH_DATETIME = datetime(1950, 1, 1)

def round_to_n(x, n):
    '''
    Round to n significant digits
    '''
    if n < 1:
        raise ValueError("number of significant digits must be >= 1")

    if type(x) in (list, tuple):
        rounded_list = []
        for xi in x:
            # Use %e format to get the n most significant digits, as a string.
            format = "%." + str(n-1) + "e"
            as_string = format % xi
            rounded_list.append(float(as_string))
        
        return rounded_list

    else:
        # Use %e format to get the n most significant digits, as a string.
        format = "%." + str(n-1) + "e"
        as_string = format % x

        return float(as_string)

def addAttributeToListItems(list_to_modify, name, value):
    '''
    For each item in list_to_modify, add new attribute name with value value.
    Useful for modyfying a django queryset before passing to a template.
    '''
    new_list = []
    for item in list_to_modify:
        new_item = item
        new_item.__setattr__(name, value)
        new_list.append(new_item)

    return new_list

#
# Methods that return checkbox selections made on the UI, called by STOQSQueryManager and MPQuery
#
def getGet_Actual_Count(kwargs):
    '''
    return state of Get Actual Count checkbox from query UI
    '''
    get_actual_count_state = False
    if kwargs.has_key('get_actual_count'):
        if kwargs['get_actual_count']:
            get_actual_count_state = True

    return get_actual_count_state

def getShow_Sigmat_Parameter_Values(kwargs):
    '''
    return state of showsigmatparametervalues checkbox from query UI
    '''
    show_sigmat_parameter_values_state = False
    if kwargs.has_key('showsigmatparametervalues'):
        if kwargs['showsigmatparametervalues']:
            show_sigmat_parameter_values_state = True

    return show_sigmat_parameter_values_state

def getShow_StandardName_Parameter_Values(kwargs):
    '''
    return state of showstandardnameparametervalues checkbox from query UI
    '''
    show_standardname_parameter_values_state = False
    if kwargs.has_key('showstandardnameparametervalues'):
        if kwargs['showstandardnameparametervalues']:
            show_standardname_parameter_values_state = True

    return show_standardname_parameter_values_state

def getShow_All_Parameter_Values(kwargs):
    '''
    return state of showallparametervalues checkbox from query UI
    '''
    show_all_parameter_values_state = False
    if kwargs.has_key('showallparametervalues'):
        if kwargs['showallparametervalues']:
            show_all_parameter_values_state = True

    return show_all_parameter_values_state

def getShow_Parameter_Platform_Data(kwargs):
    '''
    return state of Show data checkbox from query UI
    '''
    show_parameter_platform_data_state = False
    if kwargs.has_key('showparameterplatformdata'):
        if kwargs['showparameterplatformdata']:
            show_parameter_platform_data_state = True

    return show_parameter_platform_data_state

def getShow_Geo_X3D_Data(kwargs):
    '''
    return state of Show data checkbox from query UI
    '''
    show_geo_x3d_data_state = False
    logger.debug('kwargs = %s', kwargs)
    if kwargs.has_key('showgeox3ddata'):
        if kwargs['showgeox3ddata']:
            show_geo_x3d_data_state = True

    return show_geo_x3d_data_state

#
# General utility methods called by STOQSQueryManager, MPQuery, etc.
#

def getParameterGroups(dbAlias, parameter):
    '''
    Return list of ParameterGroups that parameter belongs to
    '''
    from stoqs.models import ParameterGroupParameter
    return ParameterGroupParameter.objects.using(dbAlias).filter(parameter=parameter).values_list('parametergroup__name')[0]


## {{{ http://code.activestate.com/recipes/511478/ (r1)
import math
import numpy
import functools

def percentile(N, percent, key=lambda x:x):
    """
    Find the percentile of a list of values.

    @parameter N - is a list of values. Note N MUST BE already sorted.
    @parameter percent - a float value from 0.0 to 1.0.
    @parameter key - optional key function to compute value from each element of N.

    @return - the percentile of the values
    """
    if not N:
        return None
    k = (len(N)-1) * percent
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return key(N[int(k)])
    d0 = key(N[int(f)]) * (c-k)
    d1 = key(N[int(c)]) * (k-f)
    return d0+d1

# median is 50th percentile.
median = functools.partial(percentile, percent=0.5)

## end of http://code.activestate.com/recipes/511478/ }}}

def mode(N):
    '''
    Create some bins based on the min and max of the list/array in N
    compute the histogram and then the mode of the data in N.  
    Return the edge, which is clo.
    '''
    numbins = 100
    var = numpy.array(N)
    bins = numpy.linspace(var.min(), var.max(), numbins)
    hist, bin_edges = numpy.histogram(var, bins)
    index = numpy.argmax(hist)
    if index == 0:
        return bin_edges[index]
    else:
        return (bin_edges[index] + bin_edges[index-1]) / 2.0

    


# pure-Python Douglas-Peucker line simplification/generalization
#
# this code was written by Schuyler Erle <schuyler@nocat.net> and is
#   made available in the public domain.
#
# the code was ported from a freely-licensed example at
#   http://www.3dsoftware.com/Cartography/Programming/PolyLineReduction/
#
# the original page is no longer available, but is mirrored at
#   http://www.mappinghacks.com/code/PolyLineReduction/

"""

>>> line = [(0,0),(1,0),(2,0),(2,1),(2,2),(1,2),(0,2),(0,1),(0,0)]
>>> simplify_points(line, 1.0)
[(0, 0), (2, 0), (2, 2), (0, 2), (0, 0)]

>>> line = [(0,0),(0.5,0.5),(1,0),(1.25,-0.25),(1.5,.5)]
>>> simplify_points(line, 0.25)
[(0, 0), (0.5, 0.5), (1.25, -0.25), (1.5, 0.5)]

"""

def simplify_points (pts, tolerance): 
    anchor  = 0
    floater = len(pts) - 1
    stack   = []
    keep    = set()

    stack.append((anchor, floater))  
    while stack:
        anchor, floater = stack.pop()
      
        # initialize line segment
        if pts[floater] != pts[anchor]:
            anchorX = float(pts[floater][0] - pts[anchor][0])
            anchorY = float(pts[floater][1] - pts[anchor][1])
            seg_len = math.sqrt(anchorX ** 2 + anchorY ** 2)
            # get the unit vector
            anchorX /= seg_len
            anchorY /= seg_len
        else:
            anchorX = anchorY = seg_len = 0.0
    
        # inner loop:
        max_dist = 0.0
        farthest = anchor + 1
        for i in range(anchor + 1, floater):
            dist_to_seg = 0.0
            # compare to anchor
            vecX = float(pts[i][0] - pts[anchor][0])
            vecY = float(pts[i][1] - pts[anchor][1])
            seg_len = math.sqrt( vecX ** 2 + vecY ** 2 )
            # dot product:
            proj = vecX * anchorX + vecY * anchorY
            if proj < 0.0:
                dist_to_seg = seg_len
            else: 
                # compare to floater
                vecX = float(pts[i][0] - pts[floater][0])
                vecY = float(pts[i][1] - pts[floater][1])
                seg_len = math.sqrt( vecX ** 2 + vecY ** 2 )
                # dot product:
                proj = vecX * (-anchorX) + vecY * (-anchorY)
                if proj < 0.0:
                    dist_to_seg = seg_len
                else:  # calculate perpendicular distance to line (pythagorean theorem):
                    dist_to_seg = math.sqrt(abs(seg_len ** 2 - proj ** 2))
                if max_dist < dist_to_seg:
                    max_dist = dist_to_seg
                    farthest = i

        if max_dist <= tolerance: # use line segment
            keep.add(anchor)
            keep.add(floater)
        else:
            stack.append((anchor, farthest))
            stack.append((farthest, floater))

    keep = list(keep)
    keep.sort()
    # Change from original code: add the index from the original line in the return
    return [(pts[i] + (i,)) for i in keep]

def pearsonr(x, y):
    '''
    See http://stackoverflow.com/questions/3949226/calculating-pearson-correlation-and-significance-in-python and
    http://shop.oreilly.com/product/9780596529321.do
    '''
    # Assume len(x) == len(y)
    from itertools import imap
    n = len(x)
    sum_x = float(sum(x))
    sum_y = float(sum(y))
    sum_x_sq = sum(map(lambda x: pow(x, 2), x))
    sum_y_sq = sum(map(lambda x: pow(x, 2), y))
    psum = sum(imap(lambda x, y: x * y, x, y))
    num = psum - (sum_x * sum_y/n)
    den = pow((sum_x_sq - pow(sum_x, 2) / n) * (sum_y_sq - pow(sum_y, 2) / n), 0.5)
    if den == 0: return 0
    return num / den

def postgresifySQL(query, pointFlag=False, translateGeom=False, sampleFlag=False):
    '''
    Given a generic database agnostic Django query string modify it using regular expressions to work
    on a PostgreSQL server.  If pointFlag is True then use the mappoint field for geom.  If translateGeom
    is True then translate .geom to latitude and longitude columns.
    '''
    import re

    # Get text of query to quotify for Postgresql
    q = str(query)

    # Remove double quotes from around all table and colum names
    q = q.replace('"', '')

    if not sampleFlag:
        # Add aliases for geom and gid - Activity
        q = q.replace('stoqs_activity.id', 'stoqs_activity.id as gid', 1)
        q = q.replace('= stoqs_activity.id as gid', '= stoqs_activity.id', 1)           # Fixes problem with above being applied to Sample query join
        if pointFlag:
            q = q.replace('stoqs_activity.mappoint', 'stoqs_activity.mappoint as geom')
        else:
            q = q.replace('stoqs_activity.maptrack', 'stoqs_activity.maptrack as geom')
    else:
        # Add aliases for geom and gid - Sample
        q = q.replace('stoqs_sample.id', 'stoqs_sample.id as gid', 1)
        q = q.replace('stoqs_sample.geom', 'stoqs_sample.geom as geom')

    if translateGeom:
        q = q.replace('stoqs_measurement.geom', 'ST_X(stoqs_measurement.geom) as longitude, ST_Y(stoqs_measurement.geom) as latitude')
    
    # Quotify simple things that need quotes
    QUOTE_NAMEEQUALS = re.compile('name\s+=\s+(?P<argument>\S+)')
    QUOTE_DATES = re.compile('(?P<argument>\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d)')

    q = QUOTE_NAMEEQUALS.sub(r"name = '\1'", q)
    q = QUOTE_DATES.sub(r"'\1'", q)

    # The IN ( ... ) clauses require special treatment: an IN SELECT subquery needs no quoting, only string values need quotes, and numbers need no quotes
    FIND_INS = re.compile('\sIN\s[^\)]+\)')
    items = ''
    for m in FIND_INS.findall(q):
        if m.find('SELECT') == -1:
            ##logger.debug('line = %s', m)
            FIND_ITEMS = re.compile('\((?P<argument>[^\'\)]+)\)')
            new_items = ''
            try:
                items = FIND_ITEMS.search(m).groups()[0]
            except Exception, e:
                logger.warn(e)
                continue
            else:
                for item in items.split(','):
                    if not item.isdigit():
                        new_items = new_items + "'" + item.strip() + "', "
                    else:
                        new_items = new_items + item.strip() + ", "

                ##logger.debug('items = %s', items)
            new_items = new_items[:-2]
            ##logger.debug('new_items = %s', new_items)

            if new_items:
                ##logger.debug('Replacing items = %s with new_items = %s', items, new_items)
                q = q.replace(r' IN (' + items, r' IN (' + new_items) 

    return q

def spiciness(t,s):
    """
    Return spiciness as defined by Flament (2002).
    see : http://www.satlab.hawaii.edu/spice/spice.html
    ref : A state variable for characterizing water masses and their 
          diffusive stability: spiciness. Progress in Oceanography
          Volume 54, 2002, Pages 493-501. 
    test : spice(p=0,T=15,S=33)=0.54458641375
    NB : only for valid p = 0 
    """
    B = numpy.zeros((7,6))
    B[1,1] = 0
    B[1,2] = 7.7442e-001
    B[1,3] = -5.85e-003
    B[1,4] = -9.84e-004
    B[1,5] = -2.06e-004

    B[2,1] = 5.1655e-002
    B[2,2] = 2.034e-003
    B[2,3] = -2.742e-004
    B[2,4] = -8.5e-006
    B[2,5] = 1.36e-005

    B[3,1] = 6.64783e-003
    B[3,2] = -2.4681e-004
    B[3,3] = -1.428e-005
    B[3,4] = 3.337e-005
    B[3,5] = 7.894e-006

    B[4,1] = -5.4023e-005
    B[4,2] = 7.326e-006
    B[4,3] = 7.0036e-006
    B[4,4] = -3.0412e-006
    B[4,5] = -1.0853e-006
 
    B[5,1] = 3.949e-007
    B[5,2] = -3.029e-008
    B[5,3] = -3.8209e-007
    B[5,4] = 1.0012e-007
    B[5,5] = 4.7133e-008

    B[6,1] = -6.36e-010
    B[6,2] = -1.309e-009
    B[6,3] = 6.048e-009
    B[6,4] = -1.1409e-009
    B[6,5] = -6.676e-010
    # 
    t = numpy.array(t)
    s = numpy.array(s)
    #
    coefs = B[1:7,1:6]
    sp = numpy.zeros(t.shape)
    ss = s - 35.
    bigT = numpy.ones(t.shape)
    for i in range(6):
        bigS = numpy.ones(t.shape)
        for j in range(5):
            sp+= coefs[i,j]*bigT*bigS
            bigS*= ss
        bigT*=t
    return sp

if __name__ == "__main__":
    import doctest
    doctest.testmod()

