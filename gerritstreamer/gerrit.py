from pygerrit.client import GerritClient
from pygerrit.error import GerritError
from pygerrit.events import ErrorEvent
from oslo.config import cfg
from threading import Event
import sys
import time

from gerritstreamer.openstack.common import log

LOG = log.getLogger(__name__)

cfg.CONF.register_group(cfg.OptGroup(name='gerrit'))

GERRIT_OPTS = (
    cfg.StrOpt('host', default="review", help="Gerrit SSH name in ~/.ssh/config",),
    cfg.IntOpt('port', default=29418, help="Gerrit port to connect to"),
    cfg.StrOpt('debug', default=True, help="Enable debug for the pygerrit or not"),
    cfg.IntOpt('timeout', default=None, help="What's the timeout for pygerrit?"),
    cfg.BoolOpt('ignore-stream-error', default=True, help="Ignore streamErrors"),
    cfg.IntOpt('poll_interval', default=1, help="Interval to pull Gerrit for events.")
)

cfg.CONF.register_opts(GERRIT_OPTS, group='gerrit')


class GerritEvents(object):
    def __init__(self, dispatch_func):
        self.dispatch_func = dispatch_func
        self.client = None

    def get_client(self):
        try:
            return GerritClient(host=cfg.CONF['gerrit'].host)
        except GerritError, e:
            LOG.error('Couldn\'t initialize GerritClient %s', e)

    def connect(self):
        self.client = self.get_client()
        # NOTE: For some weirdo reason pygerrit doesn't open transport unless this is done...
        self.version = self.client.gerrit_version()

    def start(self):
        # TODO: Fix error handling ? :D
        self.connect()

        LOG.info('Connected to Gerrit version: %s', self.version)

        self.client.start_event_stream()

        self.errors = Event()

        try:
            while self.client:
                event = self.client.get_event(block=False, timeout=cfg.CONF['gerrit'].timeout)
                self.dispatch(event)
        except Exception, e:
            LOG.error('Error occurred: %s', e)
            self.client.stop_eventstream()

        if self.error.isSet():
            LOG.error('Stopped')

    def dispatch(self, event):
        """
        Dispatch the event we got up to the parent for further handling
        """
        if event:
            if isinstance(event, ErrorEvent) and \
                    not cfg.CONF['gerrit'].ignore_stream_error:
                LOG.error(event.error)
                self.errors.set()
            self.dispatch_func(event)
        else:
            #LOG.debug("No event")
            time.sleep(cfg.CONF['gerrit'].poll_interval)

    def stop(self):
        LOG('STOP')
        self.client.stop_stream()
