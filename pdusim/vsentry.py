'''
*********************************************************
Copyright @ 2015 EMC Corporation All Rights Reserved
*********************************************************
'''
import select
import sys
import common.logger as logger
import basepdu


class vSentry(basepdu.vPDUBase):

    # ####PDU Action#######
    # 0 - none
    # 1 - on
    # 2 - off
    # 3 - reboot
    actions = ['none', 'on', 'off', 'reboot']

    # ####PDU State########
    # 0 - idleOff
    # 1 - idleOn
    # 2 - wakeOff
    # 3 - wakeOn
    # 4 - off
    # 5 - on
    # 6 - lockedOff
    # 7 - locakedOn
    # 8 - reboot
    # 9 - shutdown
    # 10 - pendOn
    # 11 - pendOff
    # 12 - minimumOff
    # 13 - minimumOn
    # 14 - eventOff
    # 15 - eventOn
    # 16 - eventReboot
    # 17 - eventShutdown
    states = ['idleOff', 'idleOn', 'wakeOff',
              'wakeOn', 'off', 'on',
              'lockedOff', 'lockedOn', 'reboot',
              'shutdown', 'pendOn', 'pendOff',
              'minimumOff', 'minimumOn', 'eventOff',
              'eventOn', 'eventReboot', 'eventShutdown']

    def __init__(self, oid_handler, node_control_handler, pipe=None):
        super(vSentry, self).__init__(oid_handler)
        self.outlet_action_oid_offset = "1.3.6.1.4.1.1718.3.2.3.1.11.1.1"
        self.outlet_state_oid_offset = "1.3.6.1.4.1.1718.3.2.3.1.10.1.1"
        self.max_outlets = 16
        self.__running = True
        self.__pipe = pipe
        self.__node_control_handler = node_control_handler

    def __init_outlets_state(self):
        pass

    def handle_outlet(self, args):
        '''
        1. Get current outlet state
        2. Get the current outlet action
        '''
        # self.logger.info("handle outlet {0}/{1}".format(outlet, self.pdu))
        outlet = args[0]
        action = args[1]
        logger.info("handle outlet {0}/{1}, action: {2}"
                    .format(outlet, self.pdu, self.actions[int(action)]))
        vmname = self.__node_control_handler.get_node_name(1, int(outlet))
        if vmname is None:
            self.set_outlet_field(self.outlet_action_oid_offset, outlet, 0)
            logger.error("No virtual node found for outlet {0}".format(outlet))
            return

        datastore = self.__node_control_handler.get_node_datastore(vmname)
        if datastore is None:
            self.set_outlet_field(self.outlet_action_oid_offset, outlet, 0)
            logger.error("No datastore found for virtual node {0}"
                         .format(vmname))
            return

        # action = self.get_outlet_field(self.outlet_action_oid_offset, outlet)
        state = self.get_outlet_field(self.outlet_state_oid_offset, outlet)
        if self.actions[int(action)] == 'none' or \
                self.actions[int(action)] == self.states[int(state)]:
            logger.warn("No need to execute the action: {}"
                        .format(self.actions[int(action)]))
            return

        # restore the action default to "none"
        if self.actions[int(action)] == 'on':
            # 'on' state
            self.set_outlet_field(self.outlet_state_oid_offset, outlet, 5)
            status = self.__node_control_handler.power_on_node(datastore,
                                                               vmname)
        elif self.actions[int(action)] == 'off':
            # 'off' state
            self.set_outlet_field(self.outlet_state_oid_offset, outlet, 4)
            status = self.__node_control_handler.power_off_node(datastore,
                                                                vmname)
        elif self.actions[int(action)] == 'reboot':
            # 'off' state
            self.set_outlet_field(self.outlet_state_oid_offset, outlet, 8)
            status = self.__node_control_handler.reboot_node(datastore, vmname)
            # 'on' state
            self.set_outlet_field(self.outlet_state_oid_offset, outlet, 5)
        else:
            logger.error("Unknown action: {0}".format(action))
            return

        if status != 0:
            logger.error("Failed to {0} virtual node."
                         .format(self.actions[int(action)]))
            return
        self.set_outlet_field(self.outlet_action_oid_offset, outlet, 0)

    def handle_message(self, message):
        logger.info("Got new message {0}".format(message))
        oid = message.split()[0]
        outlet = oid.split('.')[-1]
        value = message.split()[1]
        if oid.startswith(self.outlet_action_oid_offset):
            self.add_task("handle outlet {0}".format(outlet),
                          self.handle_outlet, int(outlet), value)
        else:
            logger.warn("{0} is not handled now.".format(message))

    def main_loop(self):
        rlist = []
        rlist.append(self.__pipe.inform)
        timeout = 10
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

                    self.handle_message(message)
        except KeyboardInterrupt:
            logger.error("Break by user.")
        except Exception, ex:
            logger.error("{0}: {1}".format(sys._getframe().f_code.co_name, ex))
        finally:
            logger.info("vSentry service exits.")
            self.__pipe.close()

    def stop(self):
        self.__running = False
