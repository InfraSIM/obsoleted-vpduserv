'''
*********************************************************
Copyright @ 2015 EMC Corporation All Rights Reserved
*********************************************************
'''
from abc import ABCMeta, abstractmethod
import common.config as config
import mapping_file


class VirtualNodeHandler(object):
    '''
    Virtual Node handler base class
    '''

    __metaclass__ = ABCMeta

    def __init__(self):
        self.__vnodes_control = []
        self.config_instance = config.get_conf_instance()
        self.__mfh = mapping_file.get_mapping_file_handle()

    def get_node_name(self, pdu, port):
        nodes_control_list = self.__mfh.nodes_list

        for node_list in nodes_control_list:
            datastore = node_list.keys()[0]
            for node_info in node_list[datastore]:
                if node_info['control_pdu'] == int(pdu) \
                        and node_info['control_port'] == int(port):
                    return node_info['node_name']
        return None

    def get_node_datastore(self, node_name):
        nodes_control_list = self.__mfh.nodes_list

        for node_list in nodes_control_list:
            datastore = node_list.keys()[0]
            for node_info in node_list[datastore]:
                if node_info['node_name'] == node_name:
                    return datastore
        return None

    @abstractmethod
    def power_on_node(self, *args):
        return

    @abstractmethod
    def power_off_node(self, *args):
        return

    @abstractmethod
    def reboot_node(self, *args):
        return
