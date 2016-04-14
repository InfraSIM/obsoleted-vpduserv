'''
*********************************************************
Copyright @ 2015 EMC Corporation All Rights Reserved
*********************************************************
'''
import sys
import os
import sqlite3
import shelve
from pysnmp.proto import rfc1902
from abc import ABCMeta, abstractmethod
import pdusim.common.config as config
import pdusim.common.logger as logger


class OIDBase(object):
    '''
    OID base class
    '''

    __metaclass__ = ABCMeta

    def __init__(self):
        '''
        Constructor
        '''
        self.config_instance = None

    @abstractmethod
    def query_oid_val(self, oid):
        return

    @abstractmethod
    def update_oid_val(self, oid, val):
        return

    @abstractmethod
    def query_oid_tag(self, oid):
        return

    @abstractmethod
    def update_oid_tag(self, oid, tag):
        return


class SqliteOIDHandler(OIDBase):
    def __init__(self):
        '''
        Constructor
        '''
        super(SqliteOIDHandler, self).__init__()
        self.config_instance = config.get_conf_instance()
        self.__db_file = os.path.join(self.config_instance.snmp_data_dir,
                                      self.config_instance.db_file)

    def update_oid_val(self, oid, val):
        '''
        Update value for oid
        '''
        if not os.path.exists(self.__db_file):
            logger.error("Database %s does not exist!" % self.__db_file)
            sys.exit(1)

        # open db
        conn = sqlite3.connect(self.__db_file)
        cur = conn.cursor()
        sql_oid = '.'.join(['%10s' % x for x in str(oid).split('.')])
        update_statement = 'update %s set value = \'%s\' where oid=\'%s\'' % \
            (self.config_instance.default_table_name, val, sql_oid)
        cur.execute(update_statement)
        conn.commit()
        conn.close()

    def query_oid_val(self, oid):
        '''
        Query value for oid
        '''
        if not os.path.exists(self.__db_file):
            logger.error("Database %s does not exist!" % self.__db_file)
            sys.exit(1)
        # open db
        conn = sqlite3.connect(self.__db_file)
        cur = conn.cursor()
        sql_oid = '.'.join(['%10s' % x for x in str(oid).split('.')])
        query_statement = 'select value from %s where oid=\'%s\'' % \
            (self.config_instance.default_table_name, sql_oid)
        cur.execute(query_statement)
        resultset = cur.fetchone()
        conn.close()
        if resultset:
            return resultset[0]

    def query_oid_tag(self, oid):
        '''
        Query tag for oid
        '''

        if not os.path.exists(self.__db_file):
            logger.error("Database %s does not exist!" % self.__db_file)
            sys.exit(1)
        # open db
        conn = sqlite3.connect(self.__db_file)
        cur = conn.cursor()
        sql_oid = '.'.join(['%10s' % x for x in str(oid).split('.')])
        query_statement = 'select tag from %s where oid=\'%s\'' % \
            (self.config_instance.default_table_name, sql_oid)
        cur.execute(query_statement)
        resultset = cur.fetchone()
        conn.close()
        if resultset:
            return resultset[0]

    def update_oid_tag(self, oid, tag):
        '''
        Update value for oid
        '''
        if not os.path.exists(self.__db_file):
            logger.error("Database %s does not exist!" % self.__db_file)
            sys.exit(1)

        # open db
        conn = sqlite3.connect(self.__db_file)
        cur = conn.cursor()
        sql_oid = '.'.join(['%10s' % x for x in str(oid).split('.')])
        update_statement = 'update %s set tag = \'%s\' where oid=\'%s\'' % \
            (self.config_instance.default_table_name, tag, sql_oid)
        cur.execute(update_statement)
        conn.commit()
        conn.close()


class FileOIDHandler(OIDBase):
    def __init__(self):
        '''
        Constructor
        '''
        super(FileOIDHandler, self).__init__()

        self.config_instance = config.get_conf_instance()
        self.__cache_file = os.path.join(self.config_instance.snmp_data_dir,
                                         self.config_instance.db_file)
        self.__sim_file = os.path.join(self.config_instance.snmp_data_dir,
                                       self.config_instance.sim_file)

    def __query_oid_in_cachefile(self, oid):
        value = ""
        try:
            s = shelve.open(self.__cache_file, "r")
            for key in s.keys():
                if key == oid:
                    value = s[key].prettyPrint()
                    break
            s.close()
        except:
            pass
        return value

    def query_oid_val(self, oid):
        '''
        Query value for oid
        '''
        # Lookup in cache file first
        value = self.__query_oid_in_cachefile(oid)
        if value != "":
            return value

        # Lookup in snmprec file
        # open file
        try:
            fdh = open(self.__sim_file, 'rw')

            while True:
                line = fdh.readline()
                if not line:
                    break
                # oid-type-value
                record_list = line.strip(os.linesep).split('|')
                if record_list[0] == oid:
                    fdh.close()
                    if "value" in record_list[2]:
                        val = record_list[2].split(',')[0].split('=')[1].strip()
                    else:
                        val = record_list[2]
                    return val
        except IOError as e:
            print e

        logger.error("Not found oid %s" % oid)
        return ""

    def __update_oid_in_cachefile(self, oid, val):
        found = False
        try:
            s = shelve.open(self.__cache_file, "rw", writeback=True)
            for key in s.keys():
                if oid == key:
                    found = True
                    break
            if found:
                s[key] = rfc1902.Integer(val, s[key].getTagSet(),
                                         s[key].getSubtypeSpec(),
                                         s[key].getNamedValues())
            else:
                s[oid] = rfc1902.Integer(val)

            s.sync()
            s.close()
        except:
            logger.error("Update oid in cachefile failed.")

    def update_oid_val(self, oid, val):
        '''
        Update value for oid
        '''
        # update in cache file
        self.__update_oid_in_cachefile(oid, val)

    def update_snmprec_file(self, oid, val):
        old_file = os.path.join(self.config_instance.snmp_data_dir,
                                "public.snmprec")
        new_file = os.path.join(self.config_instance.snmp_data_dir,
                                "new.snmprec")
        logger.info("update oid %s, val %s" % (oid, str(val)))
        # open file
        try:
            old_fdh = open(old_file, 'r')
            new_fdh = open(new_file, 'w')
            while True:
                line = old_fdh.readline()
                if not line:
                    break
                record_list = line.strip(os.linesep).split('|')
                if record_list[0] == oid:
                    record_list[2] = val
                    new_line = '|'.join(["%s" % x for x in record_list])
                    new_fdh.write(new_line + os.linesep)
                else:
                    new_fdh.write(line)
        except IOError as e:
            logger.error("Exception in updating snmprec file, exception: {}".
                         format(e))
            return

        new_fdh.close()
        old_fdh.close()
        os.rename(new_file, old_file)
