'''
*********************************************************
Copyright @ 2015 EMC Corporation All Rights Reserved
*********************************************************
'''
import os
import tempfile


class Pipe(object):

    inform_pipe = os.path.join(tempfile.gettempdir(), "inform")

    def __init__(self):
        if not os.path.exists(self.inform_pipe):
            os.mkfifo(self.inform_pipe)

        self.__inform = os.open(self.inform_pipe, os.O_RDONLY | os.O_NONBLOCK)

    def __enter__(self):
        return self

    def __exit__(self, exec_type, exec_value, traceback):
        if self.__inform:
            os.close(self.__inform)

    def __call__(self):
        return self.__inform

    @property
    def inform(self):
        return self.__inform

    def open(self):
        if not self.__inform:
            self.__inform = os.open(self.inform_pipe,
                                    os.O_RDONLY | os.O_NONBLOCK)

    def read(self, nbytes=-1):
        return os.read(self.__inform, nbytes)

    def close(self):
        os.close(self.__inform)
