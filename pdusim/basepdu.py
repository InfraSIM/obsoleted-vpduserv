'''
*********************************************************
Copyright @ 2015 EMC Corporation All Rights Reserved
*********************************************************
'''

import threading
import Queue
import pdusim.common.logger as logger
from pdusim.common.colors import bcolors as colors

from abc import ABCMeta, abstractmethod
import sys


class vPDUBase(threading.Thread):
    '''
    Base PDU class.
    '''
    __metaclass__ = ABCMeta

    def __init__(self, oid_handler):
        super(vPDUBase, self).__init__()
        self.__tasks_queue = Queue.Queue()
        self.__oid_handler = oid_handler

        self.__running = True
        self.__pdu = 1

        # default is 1
        self.setDaemon(1)
        self.start()
        self.__task_id = 0

    @property
    def pdu(self):
        return self.__pdu

    @pdu.setter
    def pdu(self, pdu):
        '''
        should start from 1
        '''
        if not isinstance(pdu, int):
            raise ValueError('Should be a integer')
        self.__pdu = pdu

    def split(self, val, sep):
        for x in (3, 2, 1):
            if val.find(sep*x) != -1:
                return val.split(sep*x)
        return [val]

    def set_outlet_field(self, offset, outlet, val):
        oid = '.'.join([offset, str(outlet)])
        self.__oid_handler.update_oid_val(oid, val)

    def get_outlet_field(self, offset, outlet):
        oid = '.'.join([offset, str(outlet)])
        ret = self.__oid_handler.query_oid_val(oid)
        return ret

    def set_outlet_mode(self, offset, outlet, mode):
        oid = '.'.join([offset, str(outlet)])
        ret = self.__oid_handler.query_oid_val(oid)
        if not ret:
            return

        try:
            value_settings = {}
            value_settings = \
                dict([self.split(x, '=') for x in self.split(ret, ',')])
            if 'mode' in value_settings and value_settings['mode'] == mode:
                return

            value_settings_str = \
                'mode='+mode+',value=' + str(value_settings['value'])
        except:
            value_settings_str = 'mode='+mode+',value=' + str(ret)

        self.__oid_handler.update_oid_val(oid, value_settings_str)

    def get_outlet_mode(self, offset, outlet):
        oid = '.'.join([offset, str(outlet)])

        ret = self.__oid_handler.query_oid_val(oid)
        if not ret:
            return ""

        try:
            value_settings = {}
            value_settings = \
                dict([self.split(x, '=') for x in self.split(ret, ',')])
            if 'mode' in value_settings:
                return value_settings['mode']

            return ""
        except:
            logger.warn("Mode is not set!")
            return ""

    def add_task(self, task_name, func, *args):
        '''
        tasks: (fun, args)
        '''
        task_name = "{task_name}-ID-{task_id}".\
            format(task_name=task_name, task_id=self.__task_id)
        self.__task_id += 1
        logger.info("Add task: {yellow}{task_name}{normal} for pdu {pdu}".
                    format(yellow=colors.YELLOW, task_name=task_name,
                           normal=colors.NORMAL, pdu=self.pdu))
        self.__tasks_queue.put((task_name, func, args))

    @abstractmethod
    def handle_outlet(self, args):
        '''
        Each PDU should have its own approach to control the node.
        Users should implement how to control the node per type of virtual
        PDU you are going to emulate.
        '''
        return

    @abstractmethod
    def handle_message(self, message):
        '''
        Handle message from snmp simulator.
        Regarding how to handle the message, it depends on the type of message,
        if some one runs a snmpset command, snmp simulator will receive this
        command, then inform virtual PDU handler, the message format:
        <OID> <value>.
        The message is sent by snmp simulator with pipe (/tmp/inform)
        '''
        return

    def run(self):
        while self.__running:
            try:
                task_name, func, args = self.__tasks_queue.get()
                logger.info("Running task ... {peachblow}{task_name}{normal} \
                            on thread {threadname}".
                            format(peachblow=colors.PEACHBLOW,
                                   task_name=task_name,
                                   normal=colors.NORMAL,
                                   threadname=self.getName()))
                func(args)
                self.__tasks_queue.task_done()
                logger.info("{cyan}{task_name}{normal} Done".
                            format(cyan=colors.CYAN,
                                   task_name=task_name,
                                   normal=colors.NORMAL))
            except Exception, ex:
                logger.error("{0}: {1}".
                             format(sys._getframe().f_code.co_name, ex))

    def main_loop(self):
        '''
        main entry for PDU. If you are emulating the PDU Gateway, then you can
        ignore this function.
        '''
        return

    def setup(self):
        return

    def teardown(self):
        return
