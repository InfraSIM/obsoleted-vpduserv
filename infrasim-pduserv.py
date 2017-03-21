#!/usr/bin/env python

'''
*********************************************************
Copyright @ 2015 EMC Corporation All Rights Reserved
*********************************************************
'''

import SocketServer
import time
import sys
import os
import signal
import struct
import fcntl
import ctypes
import math
import getopt
import pdusim.common.helper as helper

helper.add_third_party_to_path()

from texttable import Texttable, get_color_string, bcolors
import pdusim.password as password
import pdusim.reportip
import pdusim.common.logger as logger
from pdusim.common.colors import bcolors as colors
from pdusim.common.sshsrv import SSHHandler, command
import pdusim.common.config as config
import pdusim.common.daemon
import pdusim.mapping_file as mapping_file
import pdusim.pdusim

server_pid_file = "/var/run/pdusim/infrasim-pduserv.pid"
SIOCGIFINDEX = 0x8933
SIOCGIFFLAGS = 0x8913
SIOCSIFFLAGS = 0x8914
SIOCGIFHWADDR = 0x8927
SIOCSIFHWADDR = 0x8924
SIOCGIFADDR = 0x8915
SIOCSIFADDR = 0x8916
SIOCGIFNETMASK = 0x891B
SIOCSIFNETMASK = 0x891C
SIOCETHTOOL = 0x8946

# From linux/if.h
IFF_UP = 0x1

# From linux/socket.h
AF_UNIX = 1
AF_INET = 2

pdu_sim = None

class NetworkUtils:
    @staticmethod
    def get_ip_address(ifname):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            ifreq = struct.pack('16sH14s', ifname, AF_UNIX, '\x00'*14)
            res = fcntl.ioctl(s.fileno(), SIOCGIFADDR, ifreq)
            ip = struct.unpack('16sH2x4s8x', res)[2]
            s.close()
            return socket.inet_ntoa(ip)
        except:
            logger.error("Failed to get ip on %s" % ifname)
            return ""

    @staticmethod
    def set_ip_address(ifname, ip):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            bin_ip = socket.inet_aton(ip)
            ifreq = struct.pack('16sH2s4s8s', ifname, socket.AF_INET,
                                '\x00'*2, bin_ip, '\x00'*8)
            fcntl.ioctl(s, SIOCSIFADDR, ifreq)
            s.close()
        except:
            logger.error("Failed to set ip %s on %s" % (ip, ifname))
            print "Failed to set ip %s on %s" % (ip, ifname)

    @staticmethod
    def get_netmask_int(netmask):
        ret = 0
        for n in range(0, netmask):
            ret |= 1 << (31 - n)
        return ret

    @staticmethod
    def get_mask(mask):
        n = 0
        while True:
            if mask == 0:
                break
            mask &= (mask - 1)
            n += 1
        return n

    @staticmethod
    def convert_ip_to_int(ip):
        ip_items = ip.split('.')
        ip_int = 0
        for item in ip_items:
            ip_int = ip_int * 256 + int(item)
        return ip_int

    @staticmethod
    def convert_int_to_ip(ip_int):
        ip_items = ['0', '0', '0', '0']
        for i in range(0, 4):
            ip_items[3-i] = str(ip_int % 256)
            ip_int = int((int(ip_int) - int(ip_items[3-i])) / 256)
        return '.'.join(ip_items)

    @staticmethod
    def link_up(ifname):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ifreq = struct.pack("16sh", ifname, 0)
        flags = struct.unpack('16sh',
                              fcntl.ioctl(s.fileno(), SIOCGIFFLAGS, ifreq))[1]

        flags = flags | IFF_UP
        ifreq = struct.pack('16sh', ifname, flags)
        fcntl.ioctl(s.fileno(), SIOCSIFFLAGS, ifreq)
        s.close()

    @staticmethod
    def link_down(ifname):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ifreq = struct.pack("16sh", ifname, 0)
        flags = struct.unpack('16sh',
                              fcntl.ioctl(s.fileno(), SIOCGIFFLAGS, ifreq))[1]

        flags = flags & ~IFF_UP
        ifreq = struct.pack('16sh', ifname, flags)
        fcntl.ioctl(s.fileno(), SIOCSIFFLAGS, ifreq)
        s.close()

    @staticmethod
    def link_status(ifname):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ifreq = struct.pack("16sh", ifname, 0)
        flags = struct.unpack('16sh',
                            fcntl.ioctl(s.fileno(), SIOCGIFFLAGS, ifreq))[1]
        if flags & IFF_UP:
            return True
        else:
            return False
        s.close()

    @staticmethod
    def get_netmask(ifname):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ifreq = struct.pack('16sH14s', ifname, socket.AF_INET, '\x00'*14)
        try:
            res = fcntl.ioctl(s.fileno(), SIOCGIFNETMASK, ifreq)
        except IOError:
            s.close()
            return ""
        netmask = socket.ntohl(struct.unpack('16sH2xI8x', res)[2])
        s.close()
        return 32 - int(round(math.log(ctypes.c_uint32(~netmask).value + 1, 2), 1))

    @staticmethod
    def set_netmask(ifname, netmask):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        netmask = ctypes.c_uint32(~((2 ** (32 - netmask)) - 1)).value
        nmbytes = socket.htonl(netmask)
        ifreq = struct.pack('16sH2si8s', ifname, socket.AF_INET,
                            '\x00'*2, nmbytes, '\x00'*8)
        fcntl.ioctl(s.fileno(), SIOCSIFNETMASK, ifreq)
        s.close()

    @staticmethod
    def get_net_interfaces():
        return os.listdir("/sys/class/net")


class vPDUHandler(SSHHandler):
    WELCOME = "Welcome to vPDU server"
    PROMPT = "(vPDU) "

    def __init__(self):
        super(vPDUHandler, self).__init__()
        install_dir = helper.get_install_dir()
        self.config_instance = config.get_conf_instance() \
                               or config.Config(install_dir)
        config.set_conf_instance(self.config_instance)
        self.mapping_file_handle = mapping_file.get_mapping_file_handle() \
                                   or mapping_file.MappingFileHandle(install_dir)
        mapping_file.set_mapping_file_handle(self.mapping_file_handle)

    @command(['config'])
    def command_config(self, params):
        '''<esxi|pdu> [<list/update/add/delete> | <set/get>] [<param.1> ... < param.n>]

        configure vPDU
        ----------------------------------
        config pdu set <name>
        - set PDU name
        e.g.
        config pdu set hawk

        config pdu set database <database file>
        - set pdu database file name
        e.g.
        config pdu set database ipia.db

        config pdu set datadir <snmp data dir>
        - set snmp data directory name
        e.g.
        config pdu set datadir hawk

        config pdu list
        -list pdu configurations


        config esxi
        --------------------------------------
        config esxi list
         - list configuration

        config esxi update <option name> <value>
         - update configuration
         e.g.
            Update esxi ip address in configuration file, run below command:
            config esxi update host 10.62.59.124

            Update esxi host "username"
            config esxi update uesrname root

            Update esxi host "password"
            config esxi update password root

        config esxi add <host> <uesrname> <password>
         - add configuration
         e.g.
            Add an ESXi host information including ip, username and passowrd
            config esxi add 10.62.59.128 root 1234567

        config esxi delete
         - delete configuration
         e.g.
            Delete section "esxihost"
            config esxi delete esxihost

        Note: After update/add the configuration, please run 'config list' to
        be sure that the changes you made are correct.
        '''
        if len(params) == 0:
            return

        if params[0] == "pdu":
            if params[1] == 'set':
                if params[2] == 'name':
                    self.config_instance.pdu_name = params[3]
                elif params[2] == 'database':
                    self.config_instance.db_file = params[3]
                elif params[2] == 'datadir':
                    self.config_instance.snmp_data_dir = params[3]

                self.config_instance.update()
            elif params[1] == 'get':
                self.config_instance.init()
                table = Texttable()
                table.add_row(['name', self.config_instance.pdu_name])
                table.add_row(['database', self.config_instance.db_file])
                table.add_row(['snmp data dir',
                               self.config_instance.snmp_data_dir])
                table_str = table.draw()
                self.writeresponse(table_str)
                logger.info("\n" + table_str)
            elif params[1] == 'list':
                self.config_instance.init()
                table = Texttable()
                table.add_row(['pdu name', self.config_instance.pdu_name])
                table.add_row(['dbtype', self.config_instance.db_type])
                table.add_row(['database', self.config_instance.db_file])
                table.add_row(['snmpdata', self.config_instance.snmp_data_dir])
                table.add_row(['simfile', self.config_instance.sim_file])
                table_str = table.draw()
                self.writeresponse(table_str)
                logger.info("\n" + table_str)

            else:
                logger.error("Unknown command {0}".format(params[0]))
        elif params[0] == "esxi":
            if params[1] == "list":
                self.config_instance.init()
                esxi_info = self.config_instance.esxi_info
                if esxi_info is not None:
                    table = Texttable()
                    table.header(["esxi host", "username", "password"])
                    table.add_row([
                        get_color_string(bcolors.GREEN, esxi_info['host']),
                        get_color_string(bcolors.GREEN, esxi_info["username"]),
                        get_color_string(bcolors.GREEN, esxi_info['password'])
                    ])
                    table_str = table.draw()
                    self.writeresponse(table_str)
                    logger.info("\n" + table_str)
                    return
                else:
                    self.writeresponse("%sNo ESXi host info in configuration \
                                       file.%s" % (colors.RED, colors.NORMAL))
            elif params[1] == "update":
                if len(params[2:]) == 2:
                    esxi_info = self.config_instance.esxi_info
                    if esxi_info is not None:
                        esxi_info[params[2]] = params[3]
                        self.config_instance.update()
                    else:
                        self.writeresponse("%sNo %s found in configuration \
                            file.%s" % (colors.RED, params[1], colors.NORMAL))
            elif params[1] == "add":
                if len(params[2:]) != 3:
                    return

                if self.config_instance.esxi_info is None:
                    esxi_info = {}
                    logger.info("Adding esxi host: {0}, {1}, {2}"
                                .format(params[2], params[3], params[4]))
                    esxi_info['host'] = params[2]
                    esxi_info['username'] = params[3]
                    esxi_info['password'] = params[4]
                    self.config_instance.esxi_info = esxi_info
                    self.config_instance.update()
                else:
                    self.writeresponse("ESXi info already exists.")
            elif params[1] == "delete":
                if self.config_instance.esxi_info is not None:
                    self.config_instance.delete()
                else:
                    self.writeresponse("ESXi info already deleted.")
            else:
                self.writeresponse("unknown parameters.")
        else:
            self.writeresponse("unknown parameters: {0}.".format(params[0]))

    @command(['map'])
    def command_map(self, params):
        '''[<add/list/delete/update>] [<param.1> ... <param.n>]
        list/update/add mappings between VM name and PDU port
        map add <datastore> <vm> <pdu> <port>
         - Add an entry for VM and vPDU port
        e.g.:
            Add an entry.
            map add datastore1 vquanta_auto1 1 2

        map update <datastore> <vm> <pdu> <port>
         - update an entry for VM and vPDU port
        e.g.:
            Update an existing datastore entry
            map update datastore1 vquanta_auto1 3 1

        map delete <datastore> <vm>
         - Delete a datastore or a mapping for vm
         e.g.:
            Delete "datastore1"
            map delete datastore1

            Delete a mapping "vquanta_auto1 = 2" in datastore1
            map delete datastore1 vquanta_auto1

        map list
         - List all mappings between VMs and vPDU ports

        Note: when you are done to make changes, please run 'map list' to be
        sure eveything is correct.
        '''
        if len(params) == 0:
            return

        if params[0] == "add" or params[0] == "update":
            if len(params) != 5:
                self.writeresponse(
                    colors.RED + "Invalid parameters." + colors.NORMAL
                )
                return

            self.mapping_file_handle.update(params[1], params[2],
                                            params[3], params[4])

        elif params[0] == "delete":
            if len(params) == 2:
                self.mapping_file_handle.delete(params[1])
            elif len(params) == 3:
                self.mapping_file_handle.delete(params[1], params[2])
            else:
                self.writeresponse("Invalid parameters.")
        elif params[0] == "list":
            table = Texttable()
            table.header(["PDU", "Port", "VM Name", "Datastore"])
            table.set_cols_align(['c', 'c', 'c', 'c'])

            for node_list in self.mapping_file_handle.nodes_list:
                datastore = node_list.keys()[0]
                for ni in node_list[datastore]:
                    table.add_row([
                         get_color_string(bcolors.GREEN, ni["control_pdu"]),
                         get_color_string(bcolors.GREEN, ni["control_port"]),
                         get_color_string(bcolors.GREEN, ni['node_name']),
                         get_color_string(bcolors.GREEN, datastore)
                     ])

            self.writeresponse(table.draw())

    @command(['ip'])
    def command_ip(self, params):
        ''' [<set/get/link>] [<param.1> ... <param.n>]
        set/get interface IP address
        link up/down will bring up/down interface link.
        ip set <intf> <addr> <netmask>
        e.g.:
            Set enp0s8 address to 10.0.1.2
            ip set enp0s8 10.0.1.2 255.255.255.0

        ip get <intf>
        e.g.:
            Get enp0s8 address
            ip get enp0s8

            The output will be:
            ip address: 10.0.1.2, netmask: 255.255.255.0

        ip link list
         - list all avaialbe ethernet interfaces

        ip link <intf> status
         - Get specific interface link status

        ip link <intf> up
         - Bring up link for interface

        ip link <intf> down
         - Bring down link for interface
        '''
        if len(params) == 0:
            return

        ifname_list = NetworkUtils.get_net_interfaces()
        if params[0] == 'link':
            if params[1] == 'list':
                self.writeresponse(
                    colors.CYAN + "Available interfaces:" + colors.NORMAL
                )
                self.writeresponse(
                    colors.RED + ' '.join(ifname_list) + colors.NORMAL
                )
                return
            else:
                ifname = params[1]
                if ifname not in ifname_list:
                    logger.error("%s not exists." % ifname)
                    self.writeresponse("%s%s not exists.%s" %
                                       (colors.RED, ifname, colors.NORMAL))
                    return
                subcmd = params[2]
                if subcmd == 'up':
                    NetowrkUtils.link_up(ifname)
                elif subcmd == 'down':
                    NetworkUtils.link_down(ifname)
                elif subcmd == 'status':
                    ret = NetworkUtils.link_status(ifname)
                    if ret:
                        self.writeresponse("%s link up" % ifname)
                    else:
                        self.writeresponse("%s link down" % ifname)
                else:
                    logger.error("unknown parameters.")
        else:
            ifname = params[1]
            if ifname not in ifname_list:
                logger.error("%s not exists." % ifname)
                self.writeresponse("%s%s not exists.%s" %
                                   (colors.RED, ifname, colors.NORMAL))
                return

            if params[0] == 'get':
                ip_address = NetworkUtils.get_ip_address(ifname)
                netmask = NetworkUtils.get_netmask(ifname)
                self.writeresponse(
                    colors.GREEN + "ip address: " + ip_address +
                    ", " + "netmask: " +
                    NetworkUtils.convert_int_to_ip(NetworkUtils.get_netmask_int(netmask)) +
                    colors.NORMAL
                )
            elif params[0] == 'set':
                set_ip_address(ifname, params[2])
                if len(params) > 3:
                    netmask = params[3]
                    int_netmask = NetworkUtils.convert_ip_to_int(netmask)
                    NetworkUtils.set_netmask(ifname, NetworkUtils.get_mask(int_netmask))
                status = NetworkUtils.link_status(ifname)
                if not status:
                    NetworkUtils.link_up(ifname)
            else:
                logger.error("unknown parameters.")

    @command(['vpdu'])
    def command_vpdu(self, params):
        '''[<start/stop/restart/status>]
        Control vpdu service and get vpdu service status.
        vpdu start   - Start vPDU and SNMP simulator service
        vpdu stop    - Stop vPDU and SNMP simulator service
        vpdu restart - Restart vPDU and SNMP simulator service
        vpdu status  - Get vPDU and SNMP simulator status
        '''
        if len(params) == 0:
            return

        global pdu_sim
        logger.info("Executing action: %s" % params[0])
        if params[0] == 'start':
            if pdu_sim.is_alive():
                self.writeresponse("%svpdu service [%d] is alredy running.%s"
                                   % (colors.GREEN, pdu_sim.pid, colors.NORMAL))
            else:
                pdu_sim = pdusim.pdusim.PDUSim()
                pdu_sim.set_daemon()
                pdu_sim.start()
                time.sleep(1)
                if pdu_sim.is_alive():
                    self.writeresponse("%svpdu service [%d] is started.%s"
                                    % (colors.GREEN, pdu_sim.pid, colors.NORMAL))
        elif params[0] == 'stop':
            if not pdu_sim.is_alive():
                self.writeresponse("%svpdu service is already stopped.%s"
                                   % (colors.GREEN, colors.NORMAL))
                return

            if pdu_sim.is_alive():
                pdu_sim.stop()

            time.sleep(1)
            if not pdu_sim.is_alive():
                self.writeresponse("%svpdu service is stopped.%s"
                                    % (colors.GREEN, colors.NORMAL))

        elif params[0] == 'restart':
            if pdu_sim.is_alive():
                pdu_sim.stop()

            # Wait 1 second for snmpsim exit, and then end then check again
            time.sleep(1)

            if pdu_sim:
                pdu_sim = pdusim.pdusim.PDUSim()
                pdu_sim.set_daemon()
                pdu_sim.start()
                time.sleep(1)
                if pdu_sim.is_alive():
                    self.writeresponse("%svpdu service [%d] is restarted.%s"
                                    % (colors.GREEN, pdu_sim.pid, colors.NORMAL))
                    logger.info("vpdu service [%d] is restarted." % pdu_sim.pid)
                    return
            logger.error("Cannot restart vpdu service.")
        elif params[0] == 'status':
            if pdu_sim.is_alive() is True:
               response = "%svpdu service [%d] is running.%s" % \
                        (colors.GREEN, pdu_sim.pid, colors.NORMAL)
               self.writeresponse(response)
               logger.info(response)
            else:
                if pdu_sim.is_alive() is False:
                    response = \
                        "%svpdu service is not running.%s" % (colors.RED,
                                                            colors.NORMAL)
                    self.writeresponse(response)
                    logger.info(response)

    @command(['password', 'pass'])
    def command_password(self, params):
        '''[set/get/list] <pdu> <port> <password>

        password set <pdu> <port> <password>
        Set port password on pdu
        e.g.
        - Set password "A01" for port 1 on pdu 1
        password set 1 1 A01

        password get <pdu> <port>
        Get port password on pdu
        e.g.
        - Get password for port 1 on pdu 1
        password get 1 1

        password list <pdu>
        Display password of all ports on pdu
        e.g.
        - Display all ports password on pdu 1
        password list 1

        '''
        subcommand = params[0]
        if subcommand == 'set':
            if len(params) != 4:
                self.writeresponse("Invalid parameters.")
                return
            pdu = int(params[1])
            port = int(params[2])
            passwd = params[3]
            password.write_password(pdu, port, passwd)
        elif subcommand == 'get':
            if len(params) != 3:
                self.writeresponse("Invalid parameters.")
                return
            pdu = int(params[1])
            port = int(params[2])
            password_str = password.read_password(pdu, port)
            if password_str == "":
                self.writeresponse("Not found password.")
                return
            response = "Password is: " + password_str
            self.writeresponse(response)
        elif subcommand == 'list':
            if len(params) != 2:
                self.writeresponse("Invalid parameters.")
                return

            pdu = int(params[1])
            table = Texttable()
            table.header(["Port", "Password"])
            table.set_cols_dtype(['d', 't'])
            table.set_cols_align(['c', 'c'])
            for port_index in range(24):
                passwd = password.read_password(pdu, port_index + 1)
                if passwd == "":
                    continue
                table.add_row([port_index + 1, passwd])
            self.writeresponse(table.draw())

class vPDUServer(SocketServer.TCPServer):
    SocketServer.TCPServer.allow_reuse_address = True

def usage():
    print("Usage: {} [OPTIONS]".format(sys.argv[0]))
    print("Options are:")
    print("-d           Run in daemon")
    print("-h           Help")
    print("--logging-method=<file:file_name|stderr|stdout>")

def signal_handler(signum, frame):
    logger.info("Signal {0} receivced.".format(signum))
    if pdu_sim is not None and pdu_sim.is_alive():
        pdu_sim.stop()
    logger.info("vPDU exit.")
    sys.exit(0)

def init_signal():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

if __name__ == '__main__':
    daemon = False
    logger.initialize("pdusim", "stdout")
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   "dh",
                                   ["daemonize", "help", "logging-method="])
        for opt, arg in opts:
            if opt in ("-h", "--help"):
                usage()
                sys.exit(1)
            elif opt in ("-d", "--daemonize"):
                daemon = True
            elif opt == "--logging-method":
                logger.initialize("pdusim", *arg.split(':'))
    except getopt.GetoptError:
        usage()
        sys.exit(1)

    if daemon:
        pdusim.common.daemon.daemonize(server_pid_file)

    logger.info("vPDU started")
    init_signal()
    pdu_sim = pdusim.pdusim.PDUSim()
    pdu_sim.set_daemon()
    pdu_sim.start()
    logger.info("PDU service PID: {}".format(pdu_sim.pid))

    logger.info("Server started")
    server = vPDUHandler()
    server.serve_forever()
