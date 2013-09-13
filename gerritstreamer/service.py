import eventlet
from eventlet import tpool
from oslo.config import cfg
import sys
from stevedore.dispatch import DispatchExtensionManager

cfg.CONF.import_opt('state_path', 'gerritstreamer.paths')


from gerritstreamer import utils
from gerritstreamer.openstack.common import log
from gerritstreamer.openstack.common import service
from gerritstreamer.gerrit import GerritEvents

LOG = log.getLogger(__name__)


class EventStreamService(service.Service):
    def start(self):
        super(EventStreamService, self).start()

        LOG.debug('Starting evenstream thread')

        self.load_extenstions()

        self.gerrit = GerritEvents(self._map_gerrit)
        tpool.execute(self.gerrit.start)

    def stop(self):
        super(EventStreamService, self).stop()
        LOG.debug('Stopping eventstream')

    def load_extenstions(self):
        self.manager = DispatchExtensionManager('gerritstreamer.subscribers', lambda i: True)

    @staticmethod
    def filter_extension(ext, event):
        """
        Filter what handler the event should be run on
        """
        return isinstance(event, ext.plugin.events)

    def _from_gerrit(self, ext, event):
        ext = ext.plugin(self.gerrit)
        ext.dispatch(event)

    def _map_gerrit(self, event):
        LOG.info('Got event from Gerrit: %s' % event)
        self.manager.map(self.filter_extension, self._from_gerrit, event)


def prepare_service(argv=[]):
    #eventlet.monkey_patch()
    utils.read_config('gerritstreamer', sys.argv)

    cfg.CONF(argv[1:], project='gerritstreamer')
    log.setup('gerritstreamer')


def run():
    prepare_service(sys.argv)

    launcher = service.launch(EventStreamService())
    launcher.wait()
