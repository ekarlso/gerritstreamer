"""
Jenkins subscriber to trigger Gerrit based jobs without actually it
being connected to the gerrit in mind
"""
import jenkins
import os
from oslo.config import cfg
from paramiko import SSHConfig
from pygerrit import events

from yaml import load
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

from gerritstreamer.openstack.common import log
from gerritstreamer.subscribers.base import Subscriber
from gerritstreamer.common import ssh

import ipdb


LOG = log.getLogger(__name__)


cfg.CONF.register_group(cfg.OptGroup(name='jenkins_trigger'))
JENKINS_OPTS = (
    cfg.StrOpt('url', help="URL to Jenkins web API"),
    cfg.StrOpt('username', help="Username for Jenkins"),
    cfg.StrOpt('password', help="Password for Jenkins"),
    cfg.StrOpt('map_file', default="jobs.yaml",
               help="JSON mapping file of projects and jobs"),
    cfg.StrOpt('remote_variables_from', default='ssh',
               help="How to set the remote variables to use in GERRIT_..")
)

cfg.CONF.register_opts(JENKINS_OPTS, group='jenkins_trigger')


MAP = {
    events.ChangeMergedEvent: 'post',
    events.CommentAddedEvent: 'gate',
    events.PatchsetCreatedEvent: 'check'
}

SSH_CONFIG = ssh.get_ssh_config()
GERRIT_CONFIG = SSH_CONFIG.lookup(cfg.CONF['gerrit'].host)


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
        stream = file(cfg.CONF['jenkins_trigger'].map_file)
        self.jobs = load(stream, Loader=Loader)

    def _get_client(self):
        creds = {}
        if cfg.CONF['jenkins_trigger'].username and cfg.CONF['jenkins_trigger'].password:
            creds['username'] = cfg.CONF['jenkins_trigger'].username
            creds['password'] = cfg.CONF['jenkins_trigger'].password
        return jenkins.Jenkins(cfg.CONF['jenkins_trigger'].url, **creds)

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

    def _params_ssh(self):
        d = dict([('GERRIT_%s' % k.upper(), v) for k, v in GERRIT_CONFIG.items()])
        d['GERRIT_PROTO'] = 'ssh'
        return d

    def _params_config(self):
        return {
            'GERRIT_HOST': cfg.CONF['jenkins_trigger'].gerrit_host,
            'GERRIT_PORT': cfg.CONF['jenkins_trigger'].gerrit_port,
            'GERRIT_PROTO': cfg.CONF['jenkins_trigger'].gerrit_proto,
            'GERRIT_USER': cfg.CONF['jenkins_trigger'].gerrit_user
        }

    def get_remote_params(self, from_=None):
        """
        Get the remote variables data
        """
        from_ = from_ or cfg.CONF['jenkins_trigger'].remote_variables_from
        data = getattr(self, '_params_' + from_)()
        return data

    def dispatch(self, event):
        client = self._get_client()
        LOG.debug('Dispatch %s' % event)

        action = MAP[event.__class__]

        # NOTE: Lookup jobs and return if no jobs
        jobs = self._get_jobs(event.change.project, action)
        if not jobs:
            LOG.warn('No jobs for %s - %s' % (event.change.project, action))
            return

        params = {
            'GERRIT_PROJECT': event.change.project,
            'GERRIT_BRANCH': event.change.branch,
            'GERRIT_REFSPEC': event.patchset.ref,
            'GERRIT_EVENT_TYPE': event.name,
            'GERRIT_CHANGE_NUMBER': event.change.number,
        }

        remote_params = self.get_remote_params()
        params.update(remote_params)

        LOG.debug('Parameters set to: %s' % params)
        LOG.debug('Executing jobs: %s' % ", ".join(jobs))

        for j in jobs:
            job = Job(j)
            job.params.update(params)
            try:
                client.build_job(job.name, job.params)
            except jenkins.JenkinsException, e:
                LOG.error('Error build_job - %s', e)
