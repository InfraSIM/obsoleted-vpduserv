'''
*********************************************************
Copyright @ 2015 EMC Corporation All Rights Reserved
*********************************************************
'''
import sys
import select
import threading
import pdusim.vhawk as vhawk
import pdusim.common.logger as logger


class vIPIAppliance(object):

    def __init__(self, oid_handler, node_control_handler, pipe=None):
        self.__running = True
        self.__pipe = pipe
        self.__oid_handler = oid_handler
        self.__node_control_handler = node_control_handler
        self.pdu_num = 6
        self.__pdus = []
        self.__create()

    def __create(self):
        for pdu in range(self.pdu_num):
            vhawkpdu = None
            vhawkpdu = vhawk.vHawk(self.__oid_handler,
                                   self.__node_control_handler)
            vhawkpdu.pdu = pdu + 1
            vhawkpdu.setup()
            self.__pdus.append(vhawkpdu)

    def to_index(self, pdu_id):
        '''
        pdu_id is used in OID which defined by vendor, it shoud be:
        1, 4, 7, 10, 13, 16
        index should be: 0, 1, 2, 3, 4, 5, 6
        '''
        if isinstance(pdu_id, int):
            return pdu_id / 3 + pdu_id % 3 - 1
        raise ValueError("pdu_id should be integer.")

    def main_loop(self):
        rlist = []
        rlist.append(self.__pipe.inform)
        timeout = 10
        print "Total threads: {0}".format(threading.activeCount())
        try:
            while self.__running:
                readable, _, _ = select.select(rlist, [], [], timeout)
                if not readable:
                    continue

                if self.__pipe.inform in readable:
                    try:
                        message = self.__pipe.read(256)
                    except OSError, exc:
                        logger.warn("[Error %d] appeared at reading pipe" %
                                    exc.errno)
                        continue

                    if len(message) == 0:
                        continue

                    pdu_id = message.split()[0].split('.')[-2]
                    pdu_index = self.to_index(int(pdu_id))
                    logger.info("Assign message to pdu {0}".format(pdu_id))
                    self.__pdus[pdu_index].handle_message(message)
        except KeyboardInterrupt:
            logger.error("Break by user.")
        except Exception, ex:
            logger.error("{0}: {1}".format(sys._getframe().f_code.co_name, ex))
        finally:
            logger.info("vIPI Appliance service exits.")
            self.__pipe.close()

    def stop(self):
        self.__running = False
