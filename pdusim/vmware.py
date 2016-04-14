'''
*********************************************************
Copyright @ 2015 EMC Corporation All Rights Reserved
*********************************************************
'''
import time
import pdusim.ncbase as ncbase
import pdusim.common.logger as logger
import pdusim.common.sshclient as sshclient


class VMwareHandler(ncbase.VirtualNodeHandler):
    '''
    VMware VM handler.
    This class is used to power on/power off/ reboot virtual nodes.
    The control for VM is implemented with ESXi CLI. In the future,
    we could leverage vSphere python SDK (pyvmomi) to implement these
    functionalities.
    '''
    def __init__(self):
        '''
        Constructor
        '''
        super(VMwareHandler, self).__init__()
        self.__host_ip = None
        self.__username = None
        self.__password = None
        self.set_esxi_host_info()
        if self.__host_ip is not None:
            self.__ssh = sshclient.SSH(self.__host_ip, self.__username,
                                       self.__password)
            self.__ssh.connect()
            if self.__ssh.connected() is False:
                logger.error("Connection error for {0}@{1}".
                             format(self.__username, self.__host_ip))
            else:
                logger.info("Connection ok for {0}@{1}".
                            format(self.__username, self.__host_ip))
        else:
            logger.warn("ESXi is not set in configuration file.")

    def set_esxi_host_info(self):
        esxi_host_info = self.config_instance.esxi_info
        if esxi_host_info:
            self.__host_ip = esxi_host_info['host']
            self.__username = esxi_host_info['username']
            self.__password = esxi_host_info['password']

    def __build_command(self, datastore, vmname, action):
        '''
        Construct a command line
        '''
        command = "vim-cmd vmsvc/getallvms" + " | " \
            + "grep -w " + vmname + " | " \
            + "grep -w " + datastore + " | " \
            + "awk '{print $1}'" + " | " \
            + "xargs vim-cmd vmsvc/power." + action
        return command

    def __execute_command(self, cmd):
        '''
        Excute command
        '''
        if self.__ssh.connected() is False:
            logger.info("Connection is not connected")

        return self.__ssh.exec_command(cmd)

    def power_on_node(self, *args):
        '''
        Power on VM with ESXi CLI
        '''
        datastore = args[0]
        vmname = args[1]
        logger.info("Power on " + datastore + "/" + vmname + "...")

        command = self.__build_command(datastore, vmname, "getstate")
        status, ret = self.__execute_command(command)
        if status != 0:
            logger.error("Command failed, status : {0}".format(status))
            return status

        if "on" in ret:
            logger.info("%s already is on." % vmname)
            return 0
        command = self.__build_command(datastore, vmname, "on")
        status, ret = self.__execute_command(command)
        if status != 0:
            logger.error("Command failed, status : {0}".format(status))
            return status
        logger.info(ret.strip())
        return 0

    def power_off_node(self, *args):
        '''
        Power off VM with ESXi CLI
        '''
        datastore = args[0]
        vmname = args[1]
        logger.info("Power off " + datastore + "/" + vmname + "...")
        command = self.__build_command(datastore, vmname, "getstate")
        status, ret = self.__execute_command(command)
        if status != 0:
            logger.error("Command failed, status : {0}".format(status))
            return status

        if "off" in ret:
            logger.info("%s already is off." % vmname)
            return 0

        command = self.__build_command(datastore, vmname, "off")
        status, ret = self.__execute_command(command)
        if status != 0:
            logger.error("Command failed, status : {0}".format(status))
            return status
        logger.info(ret.strip())
        return 0

    def reboot_node(self, *args):
        '''
        Reboot VM
        '''
        datastore = args[0]
        vmname = args[1]
        logger.info("Reboot " + datastore + "/" + vmname + "...")
        status = self.power_off_node(datastore, vmname)
        if status != 0:
            return status
        # sleep 2 seconds
        time.sleep(2)
        status = self.power_on_node(datastore, vmname)
        return status
