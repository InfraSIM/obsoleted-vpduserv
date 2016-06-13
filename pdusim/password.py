'''
*********************************************************
Copyright @ 2015 EMC Corporation All Rights Reserved
*********************************************************
'''
import time
import os
import re
import common.logger as logger
import common.config as config


def read_password(pdu, port):
    try:
        password_file = config.get_conf_instance().password_file
        fd = open(password_file, 'r')
        while True:
            line = fd.readline()
            if not line:
                break

            # Ignore blank line
            if line == os.linesep:
                continue

            # Ignore comments which begins with "#"
            result_obj = re.search(r"^#.*", line)
            if result_obj:
                continue

            # The format should be:
            # <timestamp> <pdu number> <pdu port> <password>
            l = line.strip(os.linesep).split(':')
            try:
                lpdu = int(l[1])
                lport = int(l[2])
            except ValueError:
                logger.error("Converting int or float error from string.")
                return ""

            password = l[3]
            if lpdu == pdu and lport == port:
                fd.close()
                logger.info("Return password %s for PDU %d port %d" %
                            (password, pdu, port))
                return password
        fd.close()
        logger.error("Not found password for PDU %d port %d" % (pdu, port))
        return ""
    except IOError as e:
        logger.error("Error in open password file.exception: {}".format(e))
        return ""


def write_password(pdu, port, password):
    _content = ''
    try:
        matched = False
        password_file = config.get_conf_instance().password_file
        fd = open(password_file, 'r+')
        lines = fd.readlines()
        fd.close()
        for line in lines:
            # Ignore blank line
            if line == os.linesep:
                _content += line
                continue

            # Ignore comments which begins with '#'
            result_obj = re.search(r"^#.*", line)
            if result_obj:
                _content += line
                continue

            l = line.split(':')
            # If the password is already in configuration file, then update it.
            if pdu == int(l[1]) and port == int(l[2]):
                matched = True
                # Update password
                line = ':'.join([str(time.time()), str(pdu),
                                 str(port), str(password)])
                line += os.linesep
                logger.info("Update password %s for PDU %d port %d" %
                            (password, pdu, port))
            _content += line

        # If the pdu and port have not been assigned a password,
        # then added the password
        if not matched:
            new_line = ':'.join([str(time.time()), str(pdu),
                                 str(port), str(password)])
            new_line += os.linesep
            _content = _content + new_line
            logger.info("Add password %s for PDU %d port %d" %
                        (password, pdu, port))

        # Write the password settings back to the configuration file
        fd = open(config.get_conf_instance().password_file, 'w')
        fd.writelines(_content)
        fd.close()
    except IOError as e:
        logger.error("Error in open password file.exception: {}".format(e))
