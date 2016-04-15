#!/usr/bin/python

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
import subprocess
import socket
import struct
import fcntl
import ctypes
import math
import shutil
import getopt

install_data_dir = [
    os.path.join(os.environ['HOME'], '.pdusim'),
    os.path.join(sys.prefix, 'pdusim'),
    os.path.join(sys.prefix, 'share', 'pdusim'),
    os.path.join(os.path.split(__file__)[0], 'pdusim'),
    os.path.dirname(os.path.abspath(__file__))
]

for dir in install_data_dir:
    path = os.path.join(dir, 'third-party')
    if os.path.exists(path):
        for d in os.listdir(path):
            sys.path.insert(0, os.path.join(path, d))

from texttable import Texttable, get_color_string, bcolors
import pdusim.password as password
import pdusim.reportip
from pdusim.sss import SNMPSimService
import pdusim.common.logger as logger
from pdusim.common.colors import bcolors as colors
from pdusim.common.sshsrv import SSHHandler, command
import pdusim.common.config as config
import pdusim.common.daemon
import pdusim.mapping_file as mapping_file

server_pid_file = "/var/run/vpdud/server.pid"
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

config_home_dir = ""
# From linux/if.h
IFF_UP = 0x1

# From linux/socket.h
AF_UNIX = 1
AF_INET = 2


def get_vpdu_pid():
    try:
        fd = open("/var/run/vpdud/vpdud.pid", "r")
        line = fd.readline()
        pid = line.strip(os.linesep)
        fd.close()
        return int(pid)
    except:
        pass
    return -1


def start_vpdu():
    vpdu_command = "vpdud.py"
    if not os.path.exists("/usr/bin/vpdud.py") or \
            not os.path.exists("/usr/local/bin"):
        vpdu_command = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "vpdud.py")

    command = vpdu_command + " " + \
        "-d --logging-method=file:/var/log/vpdud/vpdud.log"
    logger.info(command)
    retcode = subprocess.call(command, shell=True)
    # wait service started
    time.sleep(10)
    return retcode


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


def get_netmask_int(netmask):
    ret = 0
    for n in range(0, netmask):
        ret |= 1 << (31 - n)
    return ret


def get_mask(mask):
    n = 0
    while True:
        if mask == 0:
            break
        mask &= (mask - 1)
        n += 1
    return n


def convert_ip_to_int(ip):
    ip_items = ip.split('.')
    ip_int = 0
    for item in ip_items:
        ip_int = ip_int * 256 + int(item)
    return ip_int


def convert_int_to_ip(ip_int):
    ip_items = ['0', '0', '0', '0']
    for i in range(0, 4):
        ip_items[3-i] = str(ip_int % 256)
        ip_int = int((int(ip_int) - int(ip_items[3-i])) / 256)
    return '.'.join(ip_items)


def link_up(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ifreq = struct.pack("16sh", ifname, 0)
    flags = struct.unpack('16sh',
                          fcntl.ioctl(s.fileno(), SIOCGIFFLAGS, ifreq))[1]

    flags = flags | IFF_UP
    ifreq = struct.pack('16sh', ifname, flags)
    fcntl.ioctl(s.fileno(), SIOCSIFFLAGS, ifreq)
    s.close()


def link_down(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ifreq = struct.pack("16sh", ifname, 0)
    flags = struct.unpack('16sh',
                          fcntl.ioctl(s.fileno(), SIOCGIFFLAGS, ifreq))[1]

    flags = flags & ~IFF_UP
    ifreq = struct.pack('16sh', ifname, flags)
    fcntl.ioctl(s.fileno(), SIOCSIFFLAGS, ifreq)
    s.close()


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


def set_netmask(ifname, netmask):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    netmask = ctypes.c_uint32(~((2 ** (32 - netmask)) - 1)).value
    nmbytes = socket.htonl(netmask)
    ifreq = struct.pack('16sH2si8s', ifname, socket.AF_INET,
                        '\x00'*2, nmbytes, '\x00'*8)
    fcntl.ioctl(s.fileno(), SIOCSIFNETMASK, ifreq)
    s.close()


def get_net_interfaces():
    return os.listdir("/sys/class/net")


class vPDUHandler(SSHHandler):
    WELCOME = "Welcome to vPDU server"
    PROMPT = "(vPDU) "

    def __init__(self):
        super(vPDUHandler, self).__init__()
        self.config_instance = config.get_conf_instance()
        self.mapping_file_handle = mapping_file.get_mapping_file_handle()

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

        ifname_list = get_net_interfaces()
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
                    link_up(ifname)
                elif subcmd == 'down':
                    link_down(ifname)
                elif subcmd == 'status':
                    ret = link_status(ifname)
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
                ip_address = get_ip_address(ifname)
                netmask = get_netmask(ifname)
                self.writeresponse(
                    colors.GREEN + "ip address: " + ip_address +
                    ", " + "netmask: " +
                    convert_int_to_ip(get_netmask_int(netmask)) +
                    colors.NORMAL
                )
            elif params[0] == 'set':
                set_ip_address(ifname, params[2])
                if len(params) > 3:
                    netmask = params[3]
                    int_netmask = convert_ip_to_int(netmask)
                    set_netmask(ifname, get_mask(int_netmask))
                status = link_status(ifname)
                if not status:
                    link_up(ifname)
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

        logger.info("Executing action: %s" % params[0])
        if params[0] == 'start':
            pid = get_vpdu_pid()
            logger.info("vpdu pid: %d" % pid)
            if pid > 0:
                self.writeresponse("%svpdu service [%d] is alredy running.%s"
                                   % (colors.GREEN, pid, colors.NORMAL))
            else:
                ret = start_vpdu()
                if ret == 0:
                    pid = get_vpdu_pid()
                    if pid > 0:
                        self.writeresponse("%svpdu service [%d] is started.%s"
                                           % (colors.GREEN, pid, colors.NORMAL))
                        return
                else:
                    # check if the snmpsim service is already running.
                    snmpsim_pid = SNMPSimService.getpid()
                    if snmpsim_pid > 0:
                        os.kill(snmpsim_pid, signal.SIGTERM)
                    self.writeresponse("%sFailed to start vpdu service.%s"
                                       % (colors.RED, colors.NORMAL))
                    logger.error("Failed to start vpdu service.")
        elif params[0] == 'stop':
            pid = get_vpdu_pid()
            if pid < 0:
                self.writeresponse("%svpdu service is already stopped.%s"
                                   % (colors.GREEN, colors.NORMAL))
                return

            if pid > 0:
                os.kill(pid, signal.SIGTERM)

            # Wait 1 second for snmpsim exit, and then end then check again
            time.sleep(1)
            snmpsim_pid = SNMPSimService.getpid()
            if snmpsim_pid > 0:
                os.kill(snmpsim_pid, signal.SIGTERM)

            pid = get_vpdu_pid()
            snmpsim_pid = SNMPSimService.getpid()

            if pid < 0 and snmpsim_pid < 0:
                self.writeresponse("%svpdu service is stopped.%s"
                                   % (colors.GREEN, colors.NORMAL))
            else:
                self.writeresponse("%sCannot stop vpdu service.vpdu pid %d, \
                                   snmpsim pid %d.%s"
                                   % (colors.RED, pid, snmpsim_pid,
                                      colors.NORMAL))
                logger.error("Cannot stop vpdu service. vpdu pid %d, \
                             snmpsim pid %d" % (pid, snmpsim_pid))
        elif params[0] == 'restart':
            pid = get_vpdu_pid()
            if pid > 0:
                os.kill(pid, signal.SIGTERM)

            # Wait 1 second for snmpsim exit, and then end then check again
            time.sleep(1)
            snmpsim_pid = SNMPSimService.getpid()
            if snmpsim_pid > 0:
                os.kill(snmpsim_pid, signal.SIGTERM)

            self.writeresponse("{0}vpdu service is stopped.{1}"
                               .format(colors.GREEN, colors.NORMAL))
            logger.info("vpdu service is stopped.")
            ret = start_vpdu()
            if ret == 0:
                pid = get_vpdu_pid()
                snmpsim_pid = SNMPSimService.getpid()
                if pid > 0 and snmpsim_pid > 0:
                    self.writeresponse("{0}vpdu service [{1}] is restarted.{2}"
                                       .format(colors.GREEN, pid, colors.NORMAL)
                                       )
                    logger.info("vpdu service [%d] is restarted." % pid)
                    return
            self.writeresponse("{0}Cannot restart vpdu service. pid {1}, \
                               snmpsimd pid {2}{3}".format(colors.RED, pid,
                                                           snmpsim_pid,
                                                           colors.NORMAL)
                               )
            logger.error("Cannot restart vpdu service.")
        elif params[0] == 'status':
            vpdu_pid = get_vpdu_pid()
            snmpsim_pid = SNMPSimService.getpid()
            response = ""
            if vpdu_pid > 0 and snmpsim_pid > 0:
                response = "%svpdu service [%d] is running.%s" % \
                        (colors.GREEN, vpdu_pid, colors.NORMAL)
                self.writeresponse(response)
                logger.info(response)
            elif vpdu_pid < 0 and snmpsim_pid < 0:
                response = \
                    "%svpdu service is not running.%s" % (colors.RED,
                                                          colors.NORMAL)
                self.writeresponse(response)
                logger.info(response)
            else:
                response = "{0}There is an exception, \
                    vpdu pid {1}, snmp sim pid {2}.{3}"\
                    .format(colors.RED, vpdu_pid, snmpsim_pid, colors.NORMAL)
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
            pdu = int(params[1]) * 3 - 2
            port = int(params[2])
            passwd = params[3]
            password.write_password(pdu, port, passwd)
        elif subcommand == 'get':
            if len(params) != 3:
                self.writeresponse("Invalid parameters.")
                return
            pdu = int(params[1]) * 3 - 2
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

            pdu = int(params[1]) * 3 - 2
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

    @command(["save"])
    def command_confs(self, params):
        '''
        save

        save all configurations including password, mappings, host configuration
        '''
        # save configuration file to writable disk
        if not os.path.exists("/boot/conf"):
            shutil.copytree(os.path.join(config_home_dir, "conf"), "/boot/conf")
        else:
            for path, _, files in os.walk(
                os.path.join(config_home_dir, "conf")
            ):
                for f in files:
                    shutil.copy(os.path.join(path, f), "/boot/conf")


class vPDUServer(SocketServer.TCPServer):
    SocketServer.TCPServer.allow_reuse_address = True


def signal_handler(signum, frame):
    vpdu_pid = get_vpdu_pid()
    if vpdu_pid > 0:
        os.kill(vpdu_pid, signal.SIGTERM)

    snmpsim_pid = SNMPSimService.getpid()
    if snmpsim_pid > 0:
        os.kill(snmpsim_pid, signal.SIGTERM)

    logger.info("Exit server.")
    sys.exit(0)


def init_signal():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def usage():
    print("Usage: server.py [OPTIONS]")
    print("Options are:")
    print("-d           Run in daemon")
    print("-h           Help")
    print("--logging-method=<file:file_name|stderr|stdout>")

if __name__ == '__main__':
    daemon = False
    logger.initialize("vpdud", "stdout")
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
                logger.initialize("vpdud", *arg.split(':'))
    except getopt.GetoptError:
        usage()
        sys.exit(1)

    if daemon:
        pdusim.common.daemon.daemonize(server_pid_file)

    init_signal()
    # report_ip_thread = threading.Thread(target = pdusim.reportip.rptClient)
    # report_ip_thread.start()

    # Find the conf home dir
    for dir in install_data_dir:
        path = os.path.join(dir, 'conf', 'host.conf')
        if os.path.exists(path):
            config_home_dir = dir
            break

    if config_home_dir == "":
        logger.error("Cann't find conf dir.")
        sys.exit(1)

    conf = config.Config(config_home_dir)
    config.set_conf_instance(conf)

    mapping_file.set_mapping_file_handle(
        mapping_file.MappingFileHandle(config_home_dir)
    )

    logger.info("Server started")
    server = vPDUHandler()
    server.serve_forever()
