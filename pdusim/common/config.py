'''
*********************************************************
Copyright @ 2015 EMC Corporation All Rights Reserved
*********************************************************
'''
import os
import ConfigParser
import pdusim.common.logger as logger

_conf_instance = None


class Config(object):
    default_table_name = "snmprec"

    def __init__(self, install_data_dir):
        self.__install_data_dir = install_data_dir
        self.pdu_mapping = os.path.join(install_data_dir,
                                        "conf/vm_pdu_mappings.conf")
        self.host_conf = os.path.join(install_data_dir, "conf/host.conf")
        self.password_file = os.path.join(install_data_dir, "conf/password")
        self.variation_modules_dir = os.path.join(install_data_dir, "variation")
        self.__config_parser = ConfigParser.ConfigParser()
        self.__pdu_name = ""
        self.__esxi_info = None
        self.__db_type = ""
        self.__db_file = ""
        self.__sim_file = ""
        self.__snmp_data_dir = ""
        self.init()

    @property
    def esxi_info(self):
        return self.__esxi_info

    @esxi_info.setter
    def esxi_info(self, obj):
        if not isinstance(obj, dict):
            raise ValueError("The value should be dict.")
        self.__esxi_info = obj

    @property
    def pdu_name(self):
        return self.__pdu_name

    @pdu_name.setter
    def pdu_name(self, value):
        self.__pdu_name = value

    @property
    def db_type(self):
        return self.__db_type

    @db_type.setter
    def db_type(self, value):
        self.__db_type = value

    @property
    def db_file(self):
        return self.__db_file

    @db_file.setter
    def db_file(self, value):
        self.__db_file = value

    @property
    def sim_file(self):
        return self.__sim_file

    @property
    def snmp_data_dir(self):
        return os.path.join(self.__install_data_dir,
                            "snmpdata", self.__snmp_data_dir)

    @snmp_data_dir.setter
    def snmp_data_dir(self, value):
        self.__snmp_data_dir = value

    def init(self):
        self.__config_parser.read(self.host_conf)

        try:
            for s in self.__config_parser.sections():
                if s.upper() == "ESXIHOST":
                    self.__esxi_info = \
                        {"host": self.__config_parser.get(s, "host"),
                         "username": self.__config_parser.get(s, "username"),
                         "password": self.__config_parser.get(s, "password")}
                elif s.upper() == "PDU":
                    if self.__config_parser.has_option(s, "name"):
                        self.__pdu_name = \
                            self.__config_parser.get(s, "name").upper()

                    if self.__config_parser.has_option(s, "dbtype"):
                        self.__db_type = \
                            self.__config_parser.get(s, "dbtype").upper()

                    if self.__config_parser.has_option(s, "database"):
                        self.__db_file = self.__config_parser.get(s, "database")

                    if self.__config_parser.has_option(s, "snmpdata"):
                        self.__snmp_data_dir = \
                            self.__config_parser.get(s, "snmpdata")

                    if self.__config_parser.has_option(s, "simfile"):
                        self.__sim_file = self.__config_parser.get(s, "simfile")
        except ConfigParser.NoSectionError:
            logger.error("No section %s" % s)
        except ConfigParser.NoOptionError:
            logger.error("No option host or username or password")
        except ConfigParser.DuplicateSectionError:
            logger.error("Duplicate section %s" % s)

    def update(self):
        self.__config_parser.read(self.host_conf)
        try:
            for s in self.__config_parser.sections():
                if s.upper() == "PDU":
                    if self.__config_parser.has_option(s, "name"):
                        self.__config_parser.set(s, "name", self.__pdu_name)

                    if self.__config_parser.has_option(s, "dbtype"):
                        self.__config_parser.set(s, "dbtype", self.__db_type)

                    if self.__config_parser.has_option(s, "database"):
                        self.__config_parser.set(s, "database", self.__db_file)

                    if self.__config_parser.has_option(s, "snmpdata"):
                        self.__config_parser.set(s, "snmpdata", self.__snmp_data_dir)
                elif s.upper() == "ESXIHOST":
                    self.__config_parser.set(s, "host", self.__esxi_info['host'])
                    self.__config_parser.set(s, "username", self.__esxi_info['username'])
                    self.__config_parser.set(s, "password", self.__esxi_info['password'])

            if self.__esxi_info is not None:
                if not self.__config_parser.has_section("esxihost"):
                    self.__config_parser.add_section("esxihost")
                self.__config_parser.set("esxihost", "host", self.__esxi_info['host'])
                self.__config_parser.set("esxihost", "username", self.__esxi_info['username'])
                self.__config_parser.set("esxihost", "password", self.__esxi_info['password'])
            self.__config_parser.write(open(self.host_conf, "w"))
        except Exception as ex:
            logger.error("Exception: {0}".format(ex))

    def delete(self):
        self.__config_parser.read(self.host_conf)
        try:
            self.__esxi_info = None
            self.__config_parser.remove_section("esxihost")
            self.__config_parser.write(open(self.host_conf, "w"))
        except Exception as ex:
            logger.error("Exception: {0}".format(ex))


def set_conf_instance(instance):
    global _conf_instance
    if not isinstance(instance, Config):
        logger.error("{0} is not Config object.".format(instance))
        return

    if _conf_instance:
        return

    _conf_instance = instance


def get_conf_instance():
    return _conf_instance
