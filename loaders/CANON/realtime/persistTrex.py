#!/bin/env python

import os
import sys
import datetime
import amqplib.client_0_8 as amqp
from optparse import OptionParser
import signal
import traceback
import trex_sensor_pb2
import pyproj
import logging
os.environ['DJANGO_SETTINGS_MODULE']='settings'
project_dir = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../"))  # settings.py is three dirs up
from django.conf import settings
from stoqs import models as m
from django.db.utils import IntegrityError
from django.contrib.gis.geos import LineString
from coards import to_udunits, from_udunits

logger = logging.getLogger('__main__')
logger.setLevel(logging.DEBUG)


class InterruptedBySignal:
    pass

class Consumer():
    '''A Consumer "knows" how to connect to a RabbitMQ Virtual host and create a connection to an exchange of
    a specified type, and set up a queue with a specified name and routing key.  Optional flags may be specified
    to persist the messages to a database and to treat the messages as Google Protocol Buffers.

    Credentials are read in from privateSettings
    '''

    def __init__(self, vhost = 'trackingvhost', exchange_name = '', exchange_type = '', queue_name = '', routing_key = '', dbAlias = ''):
        self.vhost = vhost
        self.exchange_name = exchange_name
        self.exchange_type = exchange_type
        self.queue_name = queue_name
        self.routing_key = routing_key
        self.dbAlias = dbAlias

        (self.connection, self.channel) = self.create_connection_and_channel(vhost)

        self.utmProj = pyproj.Proj(proj='utm',zone=10,ellps='WGS84')

        
    def create_connection_and_channel(self, vhost):
        '''Connect to RabbitMQ AMQP server based on settings we have at MBARI, return connection and channel objects.'''

        ##amqp_host = '134.89.12.92:5672' - stoqspg-dev
        ##amqp_host = 'messaging.shore.mbari.org:5672'
        amqp_host = '%s:%s' % (settings.RABBITMQ_TRACKING_HOST, settings.RABBITMQ_TRACKING_PORT,)
        logger.debug(amqp_host)
        # It seems somewhat meaningless to require vhost when (for now) the only allowed value is 'trackingvhost', but
        # the logic is kept here in case there is another virtual host that we may connect to.
        if vhost == 'trackingvhost':
            connection = amqp.Connection( host = amqp_host,
                userid = settings.RABBITMQ_TRACKING_USER,
                password = settings.RABBITMQ_TRACKING_PASSWORD,
                virtual_host = settings.RABBITMQ_TRACKING_VHOST,
                insist = False )
        else:
            logger.error('vhost must be trackingvhost')
            sys.exit(1)

        # Create our channel
        channel = connection.channel()

        return (connection, channel)


    def persistMessage(self, message):
        '''Callback function for AMQP message.  Assume that we are processing Frederic's trex sensor messages.'''
        print 'persistMessage(): Received SensorMessage object: ' 
        sm = trex_sensor_pb2.SensorMessage()
        print "persistMessage(): Length of message.body = %i" % len(message.body)
        sm.ParseFromString(message.body)
        i = 0
        measVars = ['temperature', 'salinity', 'nitrate', 'gulper_id']
        for s in sm.sample:
            i += 1
            print 20*'-'
            print "%d. %s" % (i, s)
            # Assume that every sample has utime, easting, northing, and depth (not every sample has all of the state variables)
            for mv in measVars:
                if s.HasField(mv):
                    logger.debug("utime = %d", s.utime)
                    dt = datetime.datetime.fromtimestamp(s.utime)
                    print "dt = %s" % dt
                    logger.debug("easting = %f", s.easting)
                    logger.debug("northing = %f", s.northing)
                    (lon, lat) = self.utmProj(s.easting, s.northing, inverse = True)
                    print "lat = %f" % lat
                    print "lon = %f" % lon

                    print "depth = %f" % s.depth
                    value = s.__getattribute__(mv)
                    print "%s = %f" % (mv, value)
        
                    if mv == 'gulper_id':
                        logger.info('>>> gulper_id = %s', value)
                        self.persistSample(dt, s.depth, lat, lon, mv, value)
                    else:
                        try:
                            self.persistMeasurement(dt, s.depth, lat, lon, mv, value)
                        except Exception, e:
                            logger.error("ERROR: *** Could not persist this measurement.  Is something wrong with PostgreSQL?  See details below. ***\n")
                            logger.error(e)
                            traceback.print_exc(file = sys.stdout)
                            ##sys.exit(-1)
                            print "Continuing on with processing messages..."


                print ''

            # As a test email extrapolated position to driftertrack - this will obscure sensortrack data visualization
            ##(lon, lat) = self.utmProj(s.easting, s.northing, inverse = True)
            ##subjMsg = 'TREX_pos,%f,%f,%f' % (s.utime, lon, lat)
            ##cmd = 'mutt -s %s driftertrack@mbari.org < /dev/null' % (subjMsg)
            ##print "Mailing message to driftertrack with command:\n%s" % cmd
            ##os.system(cmd);

        # Update Activity attributes with info that stoqs/query needs
        try:
            self.updateMaptrack()
            self.updateSimpleDepthTime()
        except Exception, e:
            logger.error("ERROR: *** Could not update MapTrack or SimpleDepthTime.  Is something wrong with PostgreSQL?  See details below. ***\n")
            logger.error(e)
            traceback.print_exc(file = sys.stdout)
            sys.exit(-1)


    def persistMeasurement(self, dt, depth, lat, lon, var, value):
        '''Call all of the create_ methods to properly persist this measurement in STOQS'''

        try:
            (parm, created) = m.Parameter.objects.using(self.dbAlias).get_or_create(name = var)
        except Exception, e:
            print "ERROR: *** Could not get_or_create name = '%s'.  See details below. ***\n" % var
            print e
            traceback.print_exc(file = sys.stdout)
            print "Continuing on with processing messages..."
            ##sys.exit(-1)

        meas = self.createMeasurement(dt, depth, lat, lon)
        mp = m.MeasuredParameter(measurement = meas,
                    parameter = parm,
                    datavalue = str(value))
        try:
            mp.save(using=self.dbAlias)
        except IntegrityError, e:
            logger.error("WARNING: Probably a duplicate measurement that could not be added to the DB.  Skipping it.\n", var)
            logger.error(e)
        else:
            print "saved %s = %f at %s, %f, %f, %f" % (parm, value, dt, depth, lat, lon)

        return 

    def persistSample(self, dt, depth, lat, lon, var, value):
        '''Call all of the create_ methods to properly persist this sample in STOQS'''

        sample = self.createSample(dt, depth, lat, lon, value)

        if sample:
            print "saved sample = %s" % (sample,)

        return 

    def createActivity(self, platformName, platformType, activityName, activityType):
        '''
        Create a "Dummy" placeholder activity for these realtime data.  Save the activity as a member variable.
        Before creating the Activity we also need to get_or_create a Platform and PlatformType.
        '''

        (platformType, created) = m.PlatformType.objects.using(self.dbAlias).get_or_create(name = platformType)
        self.platformType = platformType

        (platform, created) = m.Platform.objects.using(self.dbAlias).get_or_create(name = platformName, platformtype = platformType, color = 'ffff00')
        self.platform = platform

        (activityType, created) = m.ActivityType.objects.using(self.dbAlias).get_or_create(name = activityType)
        self.activityType = activityType
        (activity, created) = m.Activity.objects.using(self.dbAlias).get_or_create(name = activityName,
                    platform = self.platform,
                    startdate = datetime.datetime(2011,4,20,0,0,0),     # Hard-coded start & end times
                    enddate = datetime.datetime(2011,4,28,0,0,0))       # For April 2011 CANON activities
        self.activity = activity
                
        if self.activityType is not None:   
            self.activity.activitytype = self.activityType

        self.activity.save(using=self.dbAlias)

    def createMeasurement(self, time, depth, lat, long):
        '''
        Create and return a measurement object in the database.  The measurement object
        is created by first creating an instance of stoqs.models.Instantpoint using the activity, 
        then by creating an instance of Measurement using the Instantpoint.  A reference to 
        an instance of a stoqs.models.Measurement object is then returned.
        @param time: A valid datetime instance of a datetime object used to create the Instantpoint
        @param depth: The depth for the measurement
        @param lat: The latitude (degrees, assumed WGS84) for the measurement
        @param long: The longitude (degrees, assumed WGS84) for the measurement
        @return: An instance of stoqs.models.Measurement
        '''
        (ip, created) = m.InstantPoint.objects.using(self.dbAlias).get_or_create(activity = self.activity, timevalue = time)

        point = 'POINT(%s %s)' % (repr(long), repr(lat))
        (measurement, created) = m.Measurement.objects.using(self.dbAlias).get_or_create(instantpoint = ip, depth = repr(depth), geom = point)

        return measurement

    def createSample(self, time, depth, lat, long, value):
        '''
        Create and return a sample object in the database.  The sample object
        is created by first creating an instance of stoqs.models.Instantpoint using the activity, 
        then by creating an instance of Sample using the Instantpoint.  A reference to 
        an instance of a stoqs.models.Sample object is then returned.
        @param time: A valid datetime instance of a datetime object used to create the Instantpoint
        @param depth: The depth for the sample
        @param lat: The latitude (degrees, assumed WGS84) for the sample
        @param long: The longitude (degrees, assumed WGS84) for the sample
        @return: An instance of stoqs.models.Sample
        '''
        (ip, created) = m.InstantPoint.objects.using(self.dbAlias).get_or_create(activity = self.activity, timevalue = time)

        point = 'POINT(%s %s)' % (repr(long), repr(lat))
        (sample, created) = m.Sample.objects.using(self.dbAlias).get_or_create(instantpoint = ip, depth = repr(depth), geom = point, name = value)

        return sample

    def updateMaptrack(self):
        '''
        Read measurement geometry accumulated so far for this activity and compute a maptrack for the path
        '''
        qs = m.Measurement.objects.using(self.dbAlias).filter(instantpoint__activity = self.activity)
        linestringPoints = [q.geom for q in qs]
        if len(linestringPoints) < 2:
            return
        print "linestringPoints = %s" % linestringPoints
        path = LineString(linestringPoints).simplify(tolerance=.001)

        num_updated = m.Activity.objects.using(self.dbAlias).filter(id = self.activity.id).update(
                        maptrack = path,
                        mindepth = 0,
                        maxdepth = 100,
                        loaded_date = datetime.datetime.utcnow())

        print "Updated %d Activity" % num_updated

    def updateSimpleDepthTime(self):
        '''
        Read the time series of depth values for this activity, simplify it and insert the values in the
        SimpleDepthTime table that is related to the Activity.
        '''
        measurements = m.Measurement.objects.using(self.dbAlias).filter( instantpoint__activity=self.activity)
        for meas in measurements:
            ems = 1000 * to_udunits(meas.instantpoint.timevalue, 'seconds since 1970-01-01')
            d = float(meas.depth)
            m.SimpleDepthTime.objects.using(self.dbAlias).create(activity = self.activity, instantpoint = meas.instantpoint, depth = d, epochmilliseconds = ems)

        logger.info('Inserted %d values into SimpleDepthTime', len(measurements))

    def signalHandler(self, signum, frame):
        '''Throw exceptoin so as to gracefully close the channel if the process is killed.'''
        print "Signal %d received while at %s in %s line %s" % (signum, frame.f_code.co_name, frame.f_code.co_filename, frame.f_lineno,)
        raise InterruptedBySignal


    def setupQueue(self):
        """exchange, queue, routing_key will be used by the server to automagically initialize (as needed), but
        you will first have to manually create the user and vhost (with permissions) using rabbitmqctl"""
    
        # Create our exchange
        self.channel.exchange_declare( exchange = self.exchange_name, 
            type = self.exchange_type, 
            durable = True,
            auto_delete = False )
                                       
        # Create our Queue - with autodelete false, seems cause messages to be
        # preserved on the exchange if the consumer is down.. NOTE: setting
        # is fixed once the exchange is created, so if its ialready been run once, 
        # need to change quename and/or exchange name or is there a delete??
        self.channel.queue_declare( queue = self.queue_name , 
            durable = True,
            exclusive = False, 
            auto_delete = False)
            
        # Bind to the Queue / Exchange
        self.channel.queue_bind( queue = self.queue_name, 
            exchange = self.exchange_name,
            routing_key = self.routing_key )

        # Let AMQP know to send us messages
        # Instantiate message object setting flag on whhether to use Protocol Buffers or not
        if self.dbAlias:
            consumer_tag = self.channel.basic_consume( queue = self.queue_name, 
                no_ack = True,
                callback = self.persistMessage )
        else:
            consumer_tag = self.channel.basic_consume( queue = self.queue_name, 
                no_ack = True,
                callback = self.persistMessage )    # Note: persisMessage() is called in both cases - done this way until we're done implementing it

        # Trap on signal (e.g. kill <pid>)  and gracefully close the channel
        signal.signal(signal.SIGTERM, self.signalHandler)
    
        if self.exchange_type != 'fanout':
            print "Bound to routing key = %s in exchange '%s'." % (self.routing_key, self.exchange_name)
        else:
            print "Queue name %s configured in fanout exchange exchange %s." % (self.queue_name, self.exchange_name)
    
        print "Waiting for messages (Ctrl-C or send SIGTERM to cancel)..."
        try:
            while True:
                self.channel.wait()            

        except KeyboardInterrupt:
            print "Received KeyboardInterrupt Exception"
            self.channel.basic_cancel(consumer_tag)

        except InterruptedBySignal:
            print "Received InterruptedBySignal Exception"
            self.channel.basic_cancel(consumer_tag)
           
        # Close the channel
        self.channel.close()

        # Close our connection
        self.connection.close()
        print "RabbitMQ connection closed."


def deleteTestMessages(platformName, platformType, activityName, activityType, dbAlias):
    '''For testing query stoqs for Measurements that match the activity and delete them from the data base.
    '''

    activity = m.Activity.objects.using(dbAlias).filter(name = activityName, activitytype__name = activityType)
    qs = m.MeasuredParameter.objects.using(dbAlias).filter(measurement__instantpoint__activity__name = activityName,
                        measurement__instantpoint__activity__activitytype__name = activityType)

    if activity:
        ans = raw_input("Going to delete Activity %s and all %i measurements from it, O.K.? [N/y] " % (activity, qs.count()))

        if ans.upper() == 'Y':
            activity.delete(using=dbAlias)
            print "Activity deleted."



if __name__ == '__main__':

    parser = OptionParser(usage="""\

Synopsis: %prog --en <exchange_name> --et <exchange_type> --qn<queue_name> [--rk <routing_key> --vh <vhost> --persist <dbAlias> --testPersist <dbAlias>]

Starts a consumer for an AMQP exchange.  If the --persist option is specified then persist the
sensor track information in the messages to a STOQS database that is configured via Django.

Examples: 

   To create a new queue on the fanout exchange to display the sensor data:
     % persistTrex.py --en SensorMessagesFromTrex --et fanout --qn medusa_persist_trex --vh trackingvhost

   To persist messages to the Postgres database defined in settings.py:
     % persistTrex.py --en SensorMessagesFromTrex --et fanout --qn odss-staging_persist_trex --vh trackingvhost --persist stoqs_may2012_r

   To test with a saved Google Protobuf message:
     % persistTrex.py --testPersist stoqs_may2012_r

""")

    parser.add_option('', '--en',
        type='string', action='store',
        help="Specify Exchange Name")
    parser.add_option('', '--et',
        type='string', action='store',
        help="Specify Exchange Type")
    parser.add_option('', '--qn',
        type='string', action='store',
        help="Specify Queue Name")
    parser.add_option('', '--rk',
        type='string', action='store',
        help="Specify Routing Key")
    parser.add_option('', '--vh',
        type='string', action='store',
        help="Specify Virtual Host Key")
    parser.add_option('', '--persist',
        type='string', action='store',
        help="Specify dbAlias from the settings file where the data need to be persisted")
    parser.add_option('', '--testPersist',
        type='string', action='store',
        help="Run a test to persist a saved message to dbAlias rather than connect to a queue.")

    opts, args = parser.parse_args()

    if opts.et == 'fanout':
        if not opts.rk:
            opts.rk = opts.en   # Default routing_key to exchange_name if not specified
        if not (opts.en and opts.et and opts.qn):
            parser.error("Fanout exchange type needs --en and --qn.\n")
    elif opts.testPersist:
        # Test parsing a saved Google Protobuf message
        class Message:
            def __init__(self, body):
                self.body = body

        ##file = 'test_trex_pb_msg_300025010809770_002294.sbd'
        file = 'test_gulper_msg_300025010809770_002324.sbd'
        fh = open(file)
        deleteTestMessages('trex', 'auv', 'test_unassigned', 'test_AUV_mission', opts.testPersist)
        c = Consumer(dbAlias = opts.testPersist)
        c.createActivity('trex', 'auv', 'test_unassigned', 'test_AUV_mission')
        c.persistMessage(Message(fh.read()))
        fh.close()
        sys.exit()

    elif not (opts.en and opts.et and opts.qn and opts.rk):
        parser.error("Must include --rk option unless the exchange type is fanout.\n")


    # Create Consumer object
    c = Consumer(vhost = opts.vh, exchange_name = opts.en, exchange_type = opts.et, queue_name = opts.qn, 
        routing_key = opts.rk, dbAlias = opts.persist)

    # Create a dummy activity for this realtime data (paramaters set inside the method)
    c.createActivity('trex', 'auv', 'unassigned', 'AUV_mission')


    # Start the queue, block on waiting for messages - a Ctrl-C or Signal 15 will gracefully close the connection
    c.setupQueue()
 
