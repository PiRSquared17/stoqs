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

    def __init__(self, vhost = 'trackingvhost', exchange_name = '', exchange_type = '', queue_name = '', routing_key = '', persistFlag = False):
        self.vhost = vhost
        self.exchange_name = exchange_name
        self.exchange_type = exchange_type
        self.queue_name = queue_name
        self.routing_key = routing_key
        self.persistFlag = persistFlag

        (self.connection, self.channel) = self.create_connection_and_channel(vhost)

        self.utmProj = pyproj.Proj(proj='utm',zone=10,ellps='WGS84')

        
    def create_connection_and_channel(self, vhost):
        '''Connect to RabbitMQ AMQP server based on settings we have at MBARI, return connection and channel objects.'''

        ##amqp_host = '134.89.12.92:5672' - stoqspg-dev
        ##amqp_host = 'messaging.shore.mbari.org:5672'
        amqp_host = '%s:%s' % (settings.RABBITMQ_TRACKING_HOST, settings.RABBITMQ_TRACKING_PORT,)
        logger.debug(amqp_host)
        raw_input('paused')
        if vhost == 'canonvhost':
            connection = amqp.Connection( host = amqp_host, 
                userid = "canon", 
                password = "canon", 
                virtual_host = "canonvhost", 
                insist = False )
        elif vhost == 'trackingvhost':
            connection = amqp.Connection( host = amqp_host,
                userid = settings.RABBITMQ_TRACKING_USER,
                password = settings.RABBITMQ_TRACKING_PASSWORD,
                virtual_host = settings.RABBITMQ_TRACKING_VHOST,
                insist = False )
        else:
            print 'vhost must be either canonvhost or trackingvhost.'
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
        measVars = ['temperature', 'salinity', 'nitrate']
        for s in sm.sample:
            i += 1
            print 20*'-'
            ##print "%d. %s" % (i, s)
            # Assume that every sample has utime, easting, northing, and depth (not every sample has all of the state variables)
            for mv in measVars:
                if s.HasField(mv):
                    ##print "utime = %d" % s.utime
                    dt = datetime.datetime.fromtimestamp(s.utime)
                    print "dt = %s" % dt
                    ##print "easting = %f" % s.easting
                    ##print "northing = %f" % s.northing
                    (lon, lat) = self.utmProj(s.easting, s.northing, inverse = True)
                    print "lat = %f" % lat
                    print "lon = %f" % lon

                    print "depth = %f" % s.depth
                    value = s.__getattribute__(mv)
                    print "%s = %f" % (mv, value)

                    try:
                        self.persistMeasurement(dt, s.depth, lat, lon, mv, value)
                    except Exception, e:
                        print "ERROR: *** Could not persist this measurement.  Is something wrong with PostgreSQL?  See details below. ***\n"
                        print e
                        traceback.print_exc(file = sys.stdout)
                        sys.exit(-1)
                        ##print "Continuing on with processing messages..."

                print ''

            # As a test email extrapolated position to driftertrack - this will obscure sensortrack data visualization
            ##(lon, lat) = self.utmProj(s.easting, s.northing, inverse = True)
            ##subjMsg = 'TREX_pos,%f,%f,%f' % (s.utime, lon, lat)
            ##cmd = 'mutt -s %s driftertrack@mbari.org < /dev/null' % (subjMsg)
            ##print "Mailing message to driftertrack with command:\n%s" % cmd
            ##os.system(cmd);


    def persistMeasurement(self, dt, depth, lat, lon, var, value):
        '''Call all of the create_ methods to properly persist this measurement in STOQS'''

        try:
            (parm, created) = m.Parameter.objects.get_or_create(name = var)
        except Exception, e:
            print "ERROR: *** Could not get_or_create name = '%s'.  See details below. ***\n" % var
            print e
            traceback.print_exc(file = sys.stdout)
            sys.exit(-1)

        meas = self.createMeasurement(dt, depth, lat, lon)
        mp = m.MeasuredParameter(measurement = meas,
                    parameter = parm,
                    datavalue = str(value))
        try:
            mp.save()
        except IntegrityError, e:
            print "WARNING: Probably a duplicate measurement that could not be added to the DB.  Skipping it.\n" % var
            print e
        else:
            print "saved %s = %f at %s, %f, %f, %f" % (parm, value, dt, depth, lat, lon)

        return 


    def createActivity(self, platformName, platformType, activityName, activityType):
        '''
        Create a "Dummy" placeholder activity for these realtime data.  Save the activity as a member variable.
        Before creating the Activity we also need to get_or_create a Platform and PlatformType.
        '''

        (platformType, created) = m.PlatformType.objects.get_or_create(name = platformType)
        self.platformType = platformType

        (platform, created) = m.Platform.objects.get_or_create(name = platformName, platformtype = platformType)
        self.platform = platform

        (activityType, created) = m.ActivityType.objects.get_or_create(name = activityType)
        self.activityType = activityType
        (activity, created) = m.Activity.objects.get_or_create(name = activityName,
                    platform = self.platform,
                    startdate = datetime.datetime(2011,4,20,0,0,0),     # Hard-coded start & end times
                    enddate = datetime.datetime(2011,4,28,0,0,0))       # For April 2011 CANON activities
        self.activity = activity
                
        if self.activityType is not None:   
            self.activity.activitytype = self.activityType

        self.activity.save()

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
        (ip, created) = m.InstantPoint.objects.get_or_create(activity = self.activity, timevalue = time)

        point = 'POINT(%s %s)' % (repr(long), repr(lat))
        (measurement, created) = m.Measurement.objects.get_or_create(instantpoint = ip, depth = repr(depth), geom = point)

        return measurement

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
        if self.persistFlag:
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


def deleteTestMessages(platformName, platformType, activityName, activityType):
    '''For testing query stoqs for Measurements that match the activity and delete them from the data base.
    '''

    activity = m.Activity.objects.filter(name = activityName, activitytype__name = activityType)
    qs = m.MeasuredParameter.objects.filter(measurement__instantpoint__activity__name = activityName,
                        measurement__instantpoint__activity__activitytype__name = activityType)

    if activity:
        ans = raw_input("Going to delete Activity %s and all %i measurements from it, O.K.? [N/y] " % (activity, qs.count()))

        if ans.upper() == 'Y':
            activity.delete()
            print "Activity deleted."



if __name__ == '__main__':

    parser = OptionParser(usage="""\

Synopsis: %prog --en <exchange_name> --et <exchange_type> --qn<queue_name> [--rk <routing_key> --vh <vhost> --persist --testPersist]

Starts a consumer for an AMQP exchange.  If the --persist option is specified then persist the
sensor track information in the messages to a STOQS database that is configured via Django.

Examples: 

   To create a new queue on the fanout exchange to display the sensor data:
     % consumer.py --en SensorMessagesFromTrex --et fanout --qn persist_trex --vh trackingvhost

   To persist messages to the Postgres database defined in settings.py:
     % consumer.py --en SensorMessagesFromTrex --et fanout --qn persist_trex --vh trackingvhost --persist

   To test with a save Google Protobuf message:
     % consumer.py --testPersist

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
        action='store_true', default=False,
        help="Instead of simply echoing the message to stdout, write them to the database.")
    parser.add_option('', '--testPersist',
        action='store_true', default=False,
        help="Run a test to persist a saved message rather than connect to a queue.")

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

        file = '/home/stoqsadm/dev/MBARItracking/sensortracks/fredsProtoBuf_1.sbd'
        fh = open(file)
        deleteTestMessages('trex', 'auv', 'test_unassigned', 'test_AUV_mission')
        c = Consumer()
        c.createActivity('trex', 'auv', 'test_unassigned', 'test_AUV_mission')
        c.persistMessage(Message(fh.read()))
        fh.close()
        sys.exit()

    elif not (opts.en and opts.et and opts.qn and opts.rk):
        parser.error("Must include --rk option unless the exchange type is fanout.\n")


    # Create Consumer object
    c = Consumer(vhost = opts.vh, exchange_name = opts.en, exchange_type = opts.et, queue_name = opts.qn, 
        routing_key = opts.rk, persistFlag = opts.persist)

    # Create a dummy activity for this realtime data (paramaters set inside the method)
    c.createActivity('trex', 'auv', 'unassigned', 'AUV_mission')


    # Start the queue, block on waiting for messages - a Ctrl-C or Signal 15 will gracefully close the connection
    c.setupQueue()
 
