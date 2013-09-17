"""
Describe a basic subscriber api
"""


class Subscriber(object):
    def __init__(self, gerrit):
        self.gerrit = gerrit

    def dispatch(self, event):
        raise NotImplementedError