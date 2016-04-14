'''
*********************************************************
Copyright @ 2015 EMC Corporation All Rights Reserved
*********************************************************
'''

import ConfigParser
import pdusim.common.logger as logger
import os

_mapping_file_handle = None


class MappingFileHandle(object):

    def __init__(self, install_data_dir):
        self.__pdu_mapping = os.path.join(install_data_dir,
                                          "conf/vm_pdu_mappings.conf")
        self.__cf = ConfigParser.ConfigParser()
        self.__nodes_control_list = []
        self.init()

    @property
    def nodes_list(self):
        return self.__nodes_control_list

    #
    # [<datastore>: [{node_name: vm1, control_pdu: 1, control_port: 2], ...]
    #
    def init(self):
        self.__cf.read(self.__pdu_mapping)

        for section in self.__cf.sections():
            vm_list = {}
            vm_list[section] = []
            for option in self.__cf.options(section):
                try:
                    node_info = {}
                    pdu_port_list = self.__cf.get(section, option).split('.')
                    node_info['node_name'] = option
                    node_info['control_pdu'] = int(pdu_port_list[0])
                    node_info['control_port'] = int(pdu_port_list[1])

                    vm_list[section].append(node_info)
                except Exception as ex:
                    logger.error("Exception: {0}".format(ex))
                    continue
            self.__nodes_control_list.append(vm_list)

    def __update_control_list(self, datastore, vmname, pdu, port):
        has_datastore = False
        for node_list in self.__nodes_control_list:
            if node_list.has_key(datastore):
                node_found = False
                for node_info in node_list[datastore]:
                    if node_info['node_name'] == vmname:
                        node_info['control_pdu'] = pdu
                        node_info['control_port'] = port
                        node_found = True

                if node_found is False:
                    node_info = {}
                    node_info['node_name'] = vmname
                    node_info['control_pdu'] = pdu
                    node_info['control_port'] = port
                    node_list[datastore].append(node_info)

                has_datastore = True

        if has_datastore is False:
            vm_list = {}
            vm_list[datastore] = []
            ni = {}
            ni['node_name'] = vmname
            ni['control_pdu'] = pdu
            ni['control_port'] = port
            vm_list[datastore].append(ni)
            self.__nodes_control_list.append(vm_list)

        logger.info("Updated. nodes control list: {0}".
                    format(self.__nodes_control_list))

    def update(self, datastore, vmname, pdu, port):
        self.__update_control_list(datastore, vmname, pdu, port)
        for node_list in self.__nodes_control_list:
            datastore = node_list.keys()[0]
            if not self.__cf.has_section(datastore):
                self.__cf.add_section(datastore)

            for ni in node_list[datastore]:
                pdu_port_str = "{pdu}.{port}".\
                    format(pdu=ni["control_pdu"], port=ni["control_port"])
                self.__cf.set(datastore, ni['node_name'], pdu_port_str)

        self.__cf.write(open(self.__pdu_mapping, "w"))

    def delete(self, datastore, vmname=None):
        for node_list in self.__nodes_control_list:
            if node_list.has_key(datastore):
                if vmname is not None:
                    for ni in node_list[datastore]:
                        if ni['node_name'] == vmname:
                            node_list[datastore].remove(ni)
                            self.__cf.remove_option(datastore, vmname)
                else:
                    self.__nodes_control_list.remove(node_list)
                    self.__cf.remove_section(datastore)

        self.__cf.write(open(self.__pdu_mapping, "w"))


def set_mapping_file_handle(handle):
    global _mapping_file_handle

    if not isinstance(handle, MappingFileHandle):
        return

    if _mapping_file_handle:
        return

    _mapping_file_handle = handle


def get_mapping_file_handle():
    return _mapping_file_handle
