#!/usr/bin/python

'''
*********************************************************
Copyright @ 2015 EMC Corporation All Rights Reserved
*********************************************************
'''

import os
import sys
import signal
import getopt
import shutil

install_datadir = [
    os.path.join(os.environ['HOME'], '.pdusim'),
    os.path.join(sys.prefix, 'pdusim'),
    os.path.join(sys.prefix, 'share', 'pdusim'),
    os.path.join(os.path.split(__file__)[0], 'pdusim'),
    os.path.dirname(os.path.abspath(__file__))
]

for dir in install_datadir:
    path = os.path.join(dir, 'third-party')
    if os.path.exists(path):
        for d in os.listdir(path):
            sys.path.insert(0, os.path.join(path, d))

import pdusim.common.config as config
from pdusim.oid import FileOIDHandler, SqliteOIDHandler
import pdusim.common.logger as logger
import pdusim.vsentry as vsentry
import pdusim.vipiapp as vipiapp
from pdusim.vmware import VMwareHandler
from pdusim.sss import SNMPSimService
import pdusim.common.pipe as pipe
import pdusim.common.daemon
import pdusim.mapping_file as mapping_file

vpdu_handler = None
sim_serv = None
vpdud_pid_file = "/var/run/vpdud/vpdud.pid"


def signal_handler(signum, frame):
    logger.info("Signal {0} receivced.".format(signum))
    if vpdu_handler:
        vpdu_handler.stop()

    if sim_serv:
        sim_serv.stop()
    logger.info("vPDU exit.")
    sys.exit(0)


def init_signal():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def usage():
    print("Usage: vpdud.py [OPTIONS]")
    print("Options are:")
    print("-d           Run in daemon")
    print("-h           Help")
    print("--logging-method=<file:file_name|stderr|stdout>")


if __name__ == '__main__':
    pdu_device = ""
    daemon = False
    logger.initialize("vpdud", "stdout")
    try:
        opts, args = getopt.getopt(sys.argv[1:], "dh",
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
        pdusim.common.daemon.daemonize(vpdud_pid_file)

    logger.info("vPDU started.")

    configdir_found = False
    for dir in install_datadir:
        path = os.path.join(dir, 'conf', 'host.conf')
        if os.path.exists(path):
            configdir_found = True
            break

    if not configdir_found:
        logger.error("Don't find the configuration dir.")
        sys.exit(1)

    # Load configuration if exists
    if os.path.exists("/boot/conf"):
        for path, _, files in os.walk("/boot/conf"):
            for f in files:
                shutil.copy(os.path.join(path, f), os.path.join(dir, "conf"))

    p = pipe.Pipe()

    conf = config.Config(dir)
    config.set_conf_instance(conf)

    # Create mapping file handle
    mapping_file.set_mapping_file_handle(mapping_file.MappingFileHandle(dir))

    pdu_device = conf.pdu_name
    if pdu_device == "":
        logger.error("Not found pdu device in config file.")
        sys.exit(1)

    db_type = conf.db_type
    # Create OID handler
    if db_type == "SQLITE":
        oid_handler = SqliteOIDHandler()
    elif db_type == "WRITECACHE":
        oid_handler = FileOIDHandler()
    else:
        logger.error("DB type {} is not supported!".format(db_type))
        sys.exit(1)

    # Create VM handler
    vm_handler = VMwareHandler()

    # Create vPDU instance.
    if pdu_device == "SENTRY":
        vpdu_handler = vsentry.vSentry(oid_handler, vm_handler, p)
    else:
        vpdu_handler = vipiapp.vIPIAppliance(oid_handler, vm_handler, p)

    init_signal()

    # Create SNMP simulator service
    sim_serv = SNMPSimService()
    retcode = sim_serv.start()
    if retcode < 0:
        logger.error("Failed to start snmpsimd service!")
        sys.exit(1)

    logger.info("vPDU service started, pid %d." % os.getpid())
    vpdu_handler.main_loop()
