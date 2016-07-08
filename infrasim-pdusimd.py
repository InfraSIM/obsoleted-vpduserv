#!/usr/bin/python

'''
*********************************************************
Copyright @ 2015 EMC Corporation All Rights Reserved
*********************************************************
'''

import os
import sys
import getopt
import pdusim.common.logger as logger
import pdusim.pdusim

def usage():
    print("Usage:{} [OPTIONS]".format(sys.argv[0]))
    print("Options are:")
    print("-d           Run in daemon")
    print("-h           Help")
    print("--logging-method=<file:file_name|stderr|stdout>")


if __name__ == '__main__':
    pdu_device = ""
    daemon = False
    logger.initialize("pdusim", "stdout")
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
                logger.initialize("pdusim", *arg.split(':'))
    except getopt.GetoptError:
        usage()
        sys.exit(1)

    if daemon:
        pdusim.common.daemon.daemonize(vpdud_pid_file)

    logger.info("vPDU started.")

    pdu_sim = pdusim.pdusim.PDUSim()
    pdu_sim.start()
