import os
import sys
import common.helper as helper

helper.add_third_party_to_path()

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

    def set_daemon(self):
        self.daemon = True

    def init(self):
        dir = helper.get_install_dir()
        if not dir:
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

        # Create SNMP simulator service
        self.__snmp_sim_serv = SNMPSimService()

    def run(self):
        self.init()
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

        # when user run 'stop' command, the function will be called twice,
        # first call is originated from stop command, the second call is originated from
        # signal handler, but terminate could only be called once, so ignore
        # the exception in the second call.
        try:
            if self.is_alive():
                self.terminate()
        except Exception as ex:
            pass
