'''
*********************************************************
Copyright @ 2015 EMC Corporation All Rights Reserved
*********************************************************
'''

import re
import sshim
from functools import wraps
import pdusim.common.logger as logger


def command(names):
    def wrap(func):
        if 1 == len(names):
            func.command_name = names[0]
        elif len(names) > 1:
            func.command_name = names[0]
            func.aliases = []
            func.aliases = names[1:]

        @wraps(func)
        def func_wrapper(*args, **kwargs):

            return func(*args, **kwargs)
        return func_wrapper
    return wrap


class SSHHandler(object):
    """ SSH handlelr based on SSHIIM."""
    WELCOME = ''
    PROMPT = ''

    def __init__(self, handler=None, prompt='CMD> ', port=20022):

        self.commands = {}
        self.port = port
        if self.PROMPT:
            self.prompt = self.PROMPT
        else:
            self.prompt = prompt
        self.server = sshim.Server(self.handle_command, port=int(self.port))
        self.response = ''
        self.__running = True

        if handler is None:
            handler = self

        self.commands['HELP'] = self.command_help

        for key in dir(handler):
            cmd = getattr(handler, key)
            try:
                cmd_name = cmd.command_name
            except:
                if key[:8] == 'command_':
                    cmd_name = key[8:]
                else:
                    continue

            cmd_name = cmd_name.upper()
            self.commands[cmd_name] = cmd
            for alias in getattr(cmd, "aliases", []):
                self.commands[alias.upper()] = self.commands[cmd_name]

    def stop(self):
        """ Stop the thread."""
        self.__running = False
        self.server.stop()

    def writeresponse(self, rspstr):
        """ Save the response string."""
        self.response += rspstr

    def command_help(self, params=None):
        """ Print help information."""
        if params:
            cmd_name = params[0].upper()
            if self.commands.has_key(cmd_name):
                cmd = self.commands[cmd_name]
                doc = cmd.__doc__
                self.writeresponse(doc)
                return
            else:
                self.writeresponse('Command "%s" not is invalid \n' %
                                   cmd_name.lower())
        cmds = self.commands.keys()
        cmds.sort()
        self.writeresponse('Below command lists are supported. \n')
        for key in cmds:
            self.writeresponse('[%s] ' % key)

    def handle_command(self, script):
        """ Handle the command receive from user."""

        if self.WELCOME:
            script.writeline(self.WELCOME)

        status = 0
        channel = script.fileobj.channel
        while self.__running:
            self.response = ''
            script.write(self.prompt)
            groups = script.expect(re.compile('(?P<input>.*)')).groupdict()
            try:
                cmdline = groups['input'].encode('ascii', 'ignore').strip()
            except:
                continue

            if not cmdline or len(cmdline) == 0:
                continue

            cmd = cmdline.split()[0]

            if cmd.upper() == 'EXIT' \
                    or cmd.upper() == 'QUIT':
                script.writeline("Quit!")
                break

            params = []
            params = cmdline.split()[1:]

            try:
                self.commands[cmd.upper()](params)
            except Exception as ex:
                logger.error("Command '{0}' failed: {1}".format(cmd, ex))
                self.commands['HELP']()
                status = 127

            if len(self.response):
                lines = self.response.split('\n')
                for line in lines:
                    script.writeline(line)
            channel.send_exit_status(status)

    def serve_forever(self):
        """ Run the SSH server."""
        try:
            self.server.run()
        except KeyboardInterrupt:
            self.stop()
