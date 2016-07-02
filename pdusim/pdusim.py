import os
import sys

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

import common.config as config
from oid import FileOIDHandler, SqliteOIDHandler
import common.logger as logger
import vsentry as vsentry
import vipiapp as vipiapp
from vmware import VMwareHandler
from sss import SNMPSimService
import common.pipe as pipe
import mapping_file as mapping_file
import multiprocessing

class PDUSim(multiprocessing.Process):
    def __init__(self):
        super(PDUSim, self).__init__()
        self.daemon = False
        self.name = "vPDU Service"
        self.__vpdu_handler = None
        self.__snmp_sim_serv = None
        self.init()

    def set_daemon(self):
        self.daemon = True

    def init(self):
        configdir_found = False
        for dir in install_datadir:
            path = os.path.join(dir, 'conf', 'host.conf')
            if os.path.exists(path):
                configdir_found = True
                break

        if not configdir_found:
            logger.error("Don't find the configuration dir.")
            sys.exit(1)

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
            self.__vpdu_handler = vsentry.vSentry(oid_handler, vm_handler, p)
        else:
            self.__vpdu_handler = vipiapp.vIPIAppliance(oid_handler, vm_handler, p)

#        self._init_signal()

        # Create SNMP simulator service
        self.__snmp_sim_serv = SNMPSimService()

#    def _signal_handler(self, signum, frame):
#        logger.info("Signal {0} receivced.".format(signum))
#        if self.__vpdu_handler:
#            self.__vpdu_handler.stop()
#
#        if self.__snmp_sim_serv:
#            self.__snmp_sim_serv.stop()
#        logger.info("vPDU exit.")
#        sys.exit(0)
#
#    def _init_signal(self):
#        signal.signal(signal.SIGINT, self._signal_handler)
#        signal.signal(signal.SIGTERM, self._signal_handler)
#

    def run(self):
        retcode = self.__snmp_sim_serv.start()
        if retcode < 0:
            logger.error("Failed to start snmpsimd service!")
            sys.exit(1)

        self.__vpdu_handler.main_loop()

    def stop(self):
        if self.__vpdu_handler:
            self.__vpdu_handler.stop()

        if self.__snmp_sim_serv:
            self.__snmp_sim_serv.stop()

        if self.is_alive():
            self.terminate()
