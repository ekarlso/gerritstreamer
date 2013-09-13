"""
Jenkins subscriber to trigger Gerrit based jobs without actually it
being connected to the gerrit in mind
"""
import jenkins
from oslo.config import cfg
from pygerrit import events

from yaml import load
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

from gerritstreamer.sub_base import Subscriber
from gerritstreamer.openstack.common import log

LOG = log.getLogger(__name__)


cfg.CONF.register_group(cfg.OptGroup(name='jenkins'))
JENKINS_OPTS = (
	cfg.StrOpt('url', help="URL to Jenkins web API"),
	cfg.StrOpt('username', help="Username for Jenkins"),
	cfg.StrOpt('password', help="Password for Jenkins"),
	cfg.StrOpt('map_file', default="jobs.yaml", help="JSON mapping file of projects and jobs")
)
cfg.CONF.register_opts(JENKINS_OPTS, group='jenkins')


MAP = {
	events.ChangeMergedEvent: 'post',
	events.CommentAddedEvent: 'gate',
	events.PatchsetCreatedEvent: 'check'
}


class InvalidJob(Exception):
	pass


class Job(dict):
	def __init__(self, job_):
		job = {"name": job_} if isinstance(job_, basestring) else job_

		for key in ['params']:
			if key not in job:
				job[key] = {}
		self.update(job)

	def __getattr__(self, name):
		return self[name]


class JenkinsGerritTrigger(Subscriber):
	events = (
		events.ChangeMergedEvent, 
		events.CommentAddedEvent,
		events.PatchsetCreatedEvent)

	def __init__(self, gerrit):
		super(JenkinsGerritTrigger, self).__init__(gerrit)
		stream = file(cfg.CONF['jenkins'].map_file)
		self.jobs = load(stream, Loader=Loader)

	def _get_client(self):
		creds = {}
		if cfg.CONF['jenkins'].username and cfg.CONF['jenkins'].password:
			creds['username'] = cfg.CONF['jenkins'].username
			creds['password'] = cfg.CONF['jenkins'].password
		return jenkins.Jenkins(cfg.CONF['jenkins'].url, **creds)

	def _get_jobs(self, project, action):
		try:
			return self.jobs[project][action]
		except KeyError:
			return None

	def _get_job(self, job):
		"""
		Return the job config in as a Job()
		"""
		if isinstance(job, basestring):
			return Job({'name': job})
		elif isinstance(job, dict):
			return Job(job)
		else:
			raise InvalidJob


	def dispatch(self, event):
		client = self._get_client()
		LOG.debug('Dispatch %s' % event)

		action = MAP[event.__class__]

		# NOTE: Lookup jobs and return if no jobs
		jobs = self._get_jobs(event.change.project, action)
		if not jobs:
			return

		for j in jobs:
			job = Job(j)
			job.params.update({
				'GERRIT_PROJECT': event.change.project,
				'GERRIT_BRANCH': event.change.branch,
				'GERRIT_REFSPEC': event.patchset.ref,
				})
			try:
				client.build_job(job.name, job.params)
			except jenkins.JenkinsException, e:
				LOG.error('Error build_job - %s', e)