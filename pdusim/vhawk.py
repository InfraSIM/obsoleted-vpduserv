'''
*********************************************************
Copyright @ 2015 EMC Corporation All Rights Reserved
*********************************************************
'''
import time
import basepdu
import threading
import pdusim.password as pwd
import pdusim.common.logger as logger


class vHawk(basepdu.vPDUBase):

    actions = ['none', 'on', 'off', 'reboot', 'unknown']

    def __init__(self, oid_handler, node_control_handler):
        super(vHawk, self).__init__(oid_handler)

        # The following two offset are vendor specific
        self.pduouton_oid_offset = "1.3.6.1.4.1.3711.24.1.1.7.2.3.1.5"
        self.pduoutpwd_oid_offset = "1.3.6.1.4.1.3711.24.1.1.7.2.3.1.6"

        self.default_password = u"******"
        self.password_expired_interval = 300

        self.max_outlets = 24

        # Handler to control virtual node
        self.__node_control_handler = node_control_handler

        self.__timer_list = [None for outlet in range(self.max_outlets)]

        self.action_list = ['none' for outlet in range(self.max_outlets)]

    def __init_outlets(self):
        '''
        Put all outlets into 'error' mode when vpdu starts
        '''
        for outlet_index in range(self.max_outlets):
            on_offset = self.pduouton_oid_offset + "." + \
                str(self.to_pdu(self.pdu))
            self.set_outlet_mode(on_offset, outlet_index + 1, "error")

    def __init_outlets_password(self):
        for outlet_index in range(self.max_outlets):
            pwd_offset = self.pduoutpwd_oid_offset + "." + \
                str(self.to_pdu(self.pdu))
            self.set_outlet_field(pwd_offset, outlet_index + 1,
                                  self.default_password)

    def to_pdu(self, index):
        '''
        index 1 ~ 6
        Convert the index to PDU ID in oid which defined by vendor.
        '''
        return index * 3 - 2

    def extract(self, value_pattern):
        '''
        value_pattern could be just an integer, or something like:
        mode=normal,value=2
        '''
        try:
            value_settings = {}
            value_settings = \
                dict([self.split(x, '=') for x in self.split(value_pattern, ',')])
            if 'value' in value_settings:
                return int(value_settings['value'])
        except:
            return int(value_pattern)

    def handle_outlet(self, args):
        outlet = args[0]
        action = args[1]

        logger.info("handle outlet {0}/{1}, action: {2}".
                    format(outlet, self.pdu, self.actions[int(action)]))

        on_offset = self.pduouton_oid_offset + "." + str(self.to_pdu(self.pdu))
        action_in_oid = self.extract(self.get_outlet_field(on_offset, outlet))

        logger.warn("action: {0}, action_in_oid: {1}".
                    format(self.actions[int(action)],
                           self.actions[int(action_in_oid)]))

        vmname = self.__node_control_handler.get_node_name(int(self.pdu),
                                                           int(outlet))
        if vmname is None:
            logger.error("No virtual node found for outlet {0}".format(outlet))
            return

        datastore = self.__node_control_handler.get_node_datastore(vmname)
        if datastore is None:
            logger.error("No datastore found for virtual node {0}".
                         format(vmname))
            return

        # Make sure the action as the last one
        logger.info("last action: {0}, current action: {1}".
                    format(self.action_list[int(outlet) - 1],
                           self.actions[int(action)]))
        if self.action_list[int(outlet) - 1] == self.actions[int(action)]:
            logger.warn("No need to execute action for {0}/{1}".
                        format(outlet, self.pdu))
            return

        if self.actions[int(action)] == 'on':
            status = self.__node_control_handler.power_on_node(datastore,
                                                               vmname)
        elif self.actions[int(action)] == 'off':
            status = self.__node_control_handler.power_off_node(datastore,
                                                                vmname)
        elif self.actions[int(action)] == 'reboot':
            status = self.__node_control_handler.reboot(datastore, vmname)
        else:
            logger.error("Unknown action: {0}".format(action))

        if status != 0:
            logger.error("Failed to {0} virtual node.".
                         format(self.actions[int(action)]))
            return
        self.action_list[int(outlet) - 1] = self.actions[int(action)]

    # running in timer
    def do_password_check(self, pdu, outlet):
        logger.info("Timer is expired for {0}/{1}".format(outlet, pdu))
        on_offset = self.pduouton_oid_offset + "." + str(self.to_pdu(self.pdu))
        self.set_outlet_mode(on_offset, outlet, "error")

    def handle_password(self, args):
        outlet = args[0]
        password = args[1]
        logger.info("handle password {0}/{1}, password {2}".
                    format(outlet, self.pdu, password))
        pwd_offset = self.pduoutpwd_oid_offset + "." + str(self.to_pdu(self.pdu))
        on_offset = self.pduouton_oid_offset + "." + str(self.to_pdu(self.pdu))

        password_in_oid = self.get_outlet_field(pwd_offset, outlet)

        # set to default password
        self.set_outlet_field(pwd_offset, outlet, self.default_password)

        # Check if the password set by snmpset is in the database
        if password_in_oid != self.default_password \
                and password != password_in_oid:
            logger.error(
                "snmpset command didn't complete for password set[{0}/{1}].".
                format(password, password_in_oid)
            )
            self.set_outlet_mode(on_offset, outlet, "error")
            return

        # Read the password set by users with SSH interface
        expected_password = pwd.read_password(self.pdu, int(outlet))

        # Check if the password set with snmpset is the same as password set
        # with SSH interface
        if expected_password != password:
            logger.error("Invalid pssword for {0}/{1}".format(outlet, self.pdu))
            # If the password is not correct, put the outlet into 'error' mode
            self.set_outlet_mode(on_offset, outlet, "error")
            return

        # if the password is correct, then put the outlet into 'normal' mode
        self.set_outlet_mode(on_offset, outlet, "normal")

        logger.info("Set timer for {0}/{1}".format(outlet, self.pdu))

        # Create a new timer to put the outlet to 'error' mode at one specific
        # time. If the time exceeds password_expired_interval after the password
        # was set with snmpset, then the password should be invalid, the outlet
        # should be put into 'error' mode again.

        t = self.__timer_list[int(outlet) - 1]
        if t and t.isAlive():
            logger.info("timer is running for {0}/{1}. cancel it.".
                        format(outlet, self.pdu))
            # A new password set is comming, so we should reset the timer for
            # this outlet
            t.cancel()
            time.sleep(0.5)
            t.join()
            if not t.isAlive():
                logger.info("timer is stopped for {0}/{1}".
                            format(outlet, self.pdu))
            else:
                logger.error("Timer is still alive for {0}/{1}".
                             format(outlet, self.pdu))
                return

        t = threading.Timer(
                self.password_expired_interval,
                self.do_password_check,
                [self.pdu, outlet]
                )
        self.__timer_list[int(outlet) - 1] = t
        t.start()
        logger.info("Timer for {0}/{1} started.".format(outlet, self.pdu))

    def handle_message(self, message):
        oid = message.split()[0]
        outlet = oid.split('.')[-1]
        value = message.split()[1]
        logger.info("Handle message {0}".format(message))
        if message.startswith(self.pduouton_oid_offset):
            self.add_task("handle_outlet-{0}".
                          format(outlet), self.handle_outlet,
                          int(outlet), value)
        elif message.startswith(self.pduoutpwd_oid_offset):
            self.add_task("handle_password-{0}".
                          format(outlet), self.handle_password,
                          int(outlet), value)
        else:
            logger.warn("{0} is not handled now.".format(message))

    def setup(self):
        self.__init_outlets()
        self.__init_outlets_password()

    def teardown(self):
        pass
