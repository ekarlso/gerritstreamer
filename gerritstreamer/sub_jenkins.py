"""
Jenkins subscriber to trigger Gerrit based jobs without actually it
being connected to the gerrit in mind
"""

from gerritstreamer.sub_base import Subscriber
from gerritstreamer.openstack.common import log

LOG = log.getLogger(__name__)

from pygerrit.events import ChangeMergedEvent


class JenkinsGerritTrigger(Subscriber):
	events = (ChangeMergedEvent)

	def dispatch(self, event):
		LOG.debug('Dispatch %s' % event)