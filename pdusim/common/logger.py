'''
*********************************************************
Copyright @ 2015 EMC Corporation All Rights Reserved
*********************************************************
'''
import logging
import os
import sys
from pdusim.common.colors import bcolors as colors


class BaseLogger(object):

    def __init__(self, lid, *param):
        self._logger = logging.getLogger(lid)
        self._logger.setLevel(logging.DEBUG)
        self.initialize(*param)

    def __call__(self, s):
        self._logger.debug(s)

    def initialize(self, *param): pass


class vPDUFileLogger(BaseLogger):

    def initialize(self, *param):
        if not os.path.exists(os.path.dirname(param[0])):
            os.mkdir(os.path.dirname(param[0]))

        handler = logging.FileHandler(param[0])
        handler.setFormatter(
            logging.Formatter('%(asctime)s %(name)s: %(message)s')
        )
        self._logger.addHandler(handler)


class vPDUStreamLogger(BaseLogger):

    stream = sys.stderr

    def initialize(self, *param):
        handler = logging.StreamHandler(self.stream)
        handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
        self._logger.addHandler(handler)


class vPDUStdoutLogger(vPDUStreamLogger):
    stream = sys.stdout


class vPDUStderrLogger(vPDUStreamLogger):
    stream = sys.stderr

logging_map = {
        'file': vPDUFileLogger,
        'stdout': vPDUStdoutLogger,
        'stderr': vPDUStderrLogger
}

# _msg = lambda x: None
_msg = None


def initialize(lid, *args):
    if args[0] in logging_map:
        global _msg
        _msg = logging_map[args[0]](lid, *args[1:])


def error(error_msg):
    _msg("{0}{1}{2}".format(colors.RED, error_msg, colors.NORMAL))


def warn(warning_msg):
    _msg("{0}{1}{2}".format(colors.GREEN, warning_msg, colors.NORMAL))


def info(info_msg):
    _msg(info_msg)


def debug(debug_msg):
    _msg(debug_msg)
