import os
from paramiko import SSHConfig


def get_ssh_config(path=None):
    """
    Return a ssh configuration parsed from path.

    :param path: The path to the config to parse.
    """
    path = path or '%s/%s' % (os.environ.get('HOME'), '.ssh/config')
    fh = open(path)
    ssh = SSHConfig()
    ssh.parse(fh)
    return ssh
