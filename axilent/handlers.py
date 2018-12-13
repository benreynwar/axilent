'''
Python tools for creating and parsing AXI communications.
'''

import logging
import time

from axilent import dicts, comms

logger = logging.getLogger(__name__)


class ConnCommandHandler(object):
    '''
    This handler receives `Command` objects and sends their AXI
    commands over the passed in `Connection`.  The responses are
    then processed by the `Command` object that send them.

    This handler is useful to simplify communication with the FPGA.
    '''

    def __init__(self, conn):
        '''
        `conn`: A `Connection` object that the handler uses to communicate
                with the FPGA.
        '''
        self.conn = conn

    def send(self, command):
        '''
        Sends a Command objects to the FPGA and processes the responses.
        '''
        read_rs = []
        write_rs = []
        for ac in command.get_axi_commands():
            logger.debug('Sending command for %s.', ac.description)
            if isinstance(ac, comms.FakeWaitCommand):
                time.sleep(ac.sleep_time)
            else:
                assert(ac.readorwrite in (comms.WRITE_TYPE, comms.READ_TYPE))
                if ac.readorwrite == comms.WRITE_TYPE:
                    if ac.constant_address:
                        r = self.conn.write_repeat(
                            address=ac.start_address, data=ac.data)
                    else:
                        r = self.conn.write(address=ac.start_address, data=ac.data)
                    write_rs.append(r)
                else:
                    if ac.constant_address:
                        r = self.conn.read_repeat(address=ac.start_address, length=ac.length)
                    else:
                        r = self.conn.read(address=ac.start_address, length=ac.length)
                    read_rs.append(r)
        command.process_responses(read_rs, write_rs)


class DictCommandHandler(object):
    '''
    This handler receives `Command` objects and stores them.
    When the `make_command_dicts` method is called the handler returns
    a list of AXI master-to-slave dictionaries that specify the commands.
    It can also parse the output AXI slave-to-master dictionaries from
    a simulation.

    This handler is useful to fake communication when running simulations.
    '''

    def __init__(self):
        self.unsent_commands = []
        self.sent_commands = []

    def send(self, command):
        assert(not isinstance(command, list))
        self.unsent_commands.append(command)

    def get_axi_commands(self):
        axi_commands = []
        while self.unsent_commands:
            command = self.unsent_commands.pop(0)
            axi_commands += command.get_axi_commands()
            self.sent_commands.append(command)
        return axi_commands

    def process_responses(self, read_responses, write_responses):
        for command in self.sent_commands:
            command.process_responses(read_responses, write_responses)

    def consume_response_dicts(self, ds):
        read_responses, write_responses = dicts.axi_dicts_to_axi_responses(ds)
        self.process_responses(read_responses, write_responses)

    def make_command_dicts(self):
        acs = self.get_axi_commands()
        ads = dicts.axi_commands_to_axi_dicts(acs)
        return ads


class PYNQHandler(object):
    '''
    This handler receives `Command` objects and sends their AXI
    commands over the passed in PYNQ DefaultIP driver.

    This handler is useful to simplify communication with the FPGA.
    '''

    def __init__(self, driver):
        '''
        `driver`: A PYNQ DefaultIP driver with `read` and `write` methods.
                The passed driver has addresses indexing bytes, whereas
                this handler assumes addresses index 32 bits.
        '''
        self.driver = driver

    def send(self, command):
        '''
        Sends a Command objects to the FPGA and processes the responses.
        '''
        read_rs = []
        write_rs = []
        for ac in command.get_axi_commands():
            logger.debug('Command sent for %s.', ac.description)
            if isinstance(ac, comms.FakeWaitCommand):
                time.sleep(ac.sleep_time)
            else:
                assert(ac.readorwrite in (comms.WRITE_TYPE, comms.READ_TYPE))
                if ac.readorwrite == comms.WRITE_TYPE:
                    if ac.constant_address:
                        for d in ac.data:
                            self.driver.write(ac.start_address*4, d)
                            write_rs.append(comms.AxiResponse(length=1, data=[None], resp=0))
                    else:
                        for offset, d in enumerate(ac.data):
                            self.driver.write((ac.start_address+offset)*4, d)
                            write_rs.append(comms.AxiResponse(length=1, data=[None], resp=0))
                else:
                    if ac.constant_address:
                        for index in range(ac.length):
                            response = self.driver.read(ac.start_address*4)
                            read_rs.append(comms.AxiResponse(length=1, data=[response], resp=0))
                    else:
                        for index in range(ac.length):
                            response = self.driver.read((ac.start_address+index)*4)
                            read_rs.append(comms.AxiResponse(length=1, data=[response], resp=0))
        command.process_responses(read_rs, write_rs)
