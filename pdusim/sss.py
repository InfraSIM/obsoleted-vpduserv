'''
*********************************************************
Copyright @ 2015 EMC Corporation All Rights Reserved
*********************************************************
'''
import os
import subprocess
import time
import signal
import common.logger as logger
import common.config as config

snmpsim_pid_file = "/var/run/snmpsim/snmpsimd.pid"


class SNMPSimService(object):
    def __init__(self):
        self.__config_instance = config.get_conf_instance()
        self.__pdu_name = self.__config_instance.pdu_name
        self.__db_type = self.__config_instance.db_type

    @staticmethod
    def getpid():
        try:
            with open(snmpsim_pid_file, "r") as fd:
                line = fd.readline()
                pid = line.strip(os.linesep)
                return int(pid)
        except Exception:
            pass
        return -1

    def __alive(self):
        pid = self.getpid()
        if pid > 0:
            return True
        return False

    def start(self):
        if not os.path.exists('/usr/bin/snmpsimd.py') \
                and not os.path.exists('/bin/snmpsimd.py') \
                and not os.path.exists('/usr/local/bin/snmpsimd.py'):
            logger.error("snmpsimd.py does not exist!")
            return -1

        if self.__alive():
            self.stop()

        if not os.path.exists("/var/run/snmpsim"):
            os.mkdir("/var/run/snmpsim")

        if not os.path.exists("/var/log/snmpsim"):
            os.mkdir("/var/log/snmpsim")

        data_dir = self.__config_instance.snmp_data_dir
        db_path = os.path.join(data_dir, self.__config_instance.db_file)

        args_list = ["snmpsimd.py"]
        endpoint_param = "--agent-udpv4-endpoint=0.0.0.0"
        args_list.append(endpoint_param)
        process_user = "--process-user=root"
        args_list.append(process_user)
        process_group = "--process-group=root"
        args_list.append(process_group)
        logging_option = "--logging-method=file:/var/log/snmpsim/snmpsimd.log"
        args_list.append(logging_option)
        pid_option = "--pid-file=" + snmpsim_pid_file
        args_list.append(pid_option)
        daemonize_option = "--daemonize"
        args_list.append(daemonize_option)
        data_dir_option = "--data-dir=" + data_dir
        args_list.append(data_dir_option)
        if self.__db_type == "SQLITE":
            variation_modules_dir = "--variation-modules-dir=" + \
                self.__config_instance.variation_modules_dir
            args_list.append(variation_modules_dir)
            sql_option = "--variation-module-options=sql:dbtype:sqlite3,database:" + db_path
            args_list.append(sql_option)
        elif self.__db_type == "WRITECACHE":
            writecache_option = "--variation-module-options=writecache:file:" + db_path
            args_list.append(writecache_option)
        else:
            return -1

        logger.info("Start snmpsimd service for {0}.".format(self.__pdu_name))
        logger.info(' '.join(args_list))
        retcode = subprocess.call(args_list)
        if retcode != 0:
            return -1

        time.sleep(1)
        pid = self.getpid()
        if pid < 0:
            logger.error("Failed to start snmpsim service!")
            return -1

        logger.info("Succeed to start snmpsim service, pid: %d." % pid)
        return 0

    def stop(self):
        # kill the service if already run
        pid = self.getpid()
        if pid < 0:
            logger.info("snmpsim service is not running.")
            return

        os.kill(pid, signal.SIGTERM)
        logger.info("Snmpsim service [%d] exit." % pid)
