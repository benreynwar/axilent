'''
Python tools for creating and parsing AXI communications.
'''

import asyncio
import logging
import time
import random
import collections

from slvcodec import test_utils, event
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


class ReadFuture(asyncio.Future):

    def __init__(self):
        super().__init__(loop=event.LOOP)


class WriteFuture(asyncio.Future):

    def __init__(self):
        super().__init__(loop=event.LOOP)


class ReadException(Exception):

    def __init__(resp, data=None):
        self.resp = resp
        self.data = data


class WriteException(Exception):

    def __init__(resp):
        self.resp = resp


class NamedPipeHandler(object):
    '''
    This handler receives `Command` objects.
    These command objects are translated into axi commands that are
    sent to a simulator over named pipes.
    '''

    def __init__(self, dut, loop, in_name, out_name, default_inputs=None):
        if default_inputs is None:
            default_inputs = {'reset': 0}
        self.default_inputs = default_inputs
        self.loop = loop
        self.sent_commands = collections.deque()
        self.in_name = in_name
        self.out_name = out_name
        self.unsent_read_addresses = collections.deque()
        self.unsent_write_addresses = collections.deque()
        self.unsent_write_datas = collections.deque()
        self.read_futures = collections.deque()
        self.write_futures = collections.deque()
        self.dut = dut
        self.loop = loop
        self.active = False

    def set_input(self, ipt, name, value):
        if self.in_name not in ipt:
            ipt[self.in_name] = {}
        ipt[self.in_name][name] = value

    def get_output(self, opt, name):
        assert self.out_name in opt
        return opt[self.out_name][name]

    async def write(self, address, value):
        if not self.active:
            self.loop.create_task(self.communicate())
            self.active = True
        self.unsent_write_addresses.append(address)
        self.unsent_write_datas.append(value)
        write_future = WriteFuture()
        self.write_futures.append(write_future)
        await write_future

    async def read(self, address):
        if not self.active:
            self.loop.create_task(self.communicate())
            self.active = True
        self.unsent_read_addresses.append(address)
        read_future = ReadFuture()
        self.read_futures.append(read_future)
        await read_future
        return read_future.result()

    def random_address(self):
        return random.randint(0, pow(2, 32)-1)

    def random_data(self):
        return random.randint(0, pow(2, 32)-1)

    async def communicate(self):
        ar_valid = 0
        aw_valid = 0
        w_valid = 0
        ar_ready = 0
        aw_ready = 0
        w_ready = 0
        while self.read_futures or self.write_futures:
            if (ar_valid == 0) or (ar_ready == 1):
                if self.unsent_read_addresses:
                    ar_valid = 1
                    ar_addr = self.unsent_read_addresses.popleft()
                else:
                    ar_valid = 0
                    ar_addr = self.random_address()
            if (aw_valid == 0) or (aw_ready == 1):
                if self.unsent_write_addresses:
                    aw_valid = 1
                    aw_addr = self.unsent_write_addresses.popleft()
                else:
                    aw_valid = 0
                    aw_addr = self.random_address()
            if (w_valid == 0) or (w_ready == 1):
                if self.unsent_write_datas:
                    w_valid = 1
                    w_data = self.unsent_write_datas.popleft()
                else:
                    w_valid = 0
                    w_data = self.random_data()
            r_ready = random.randint(0, 1)
            b_ready = random.randint(0, 1)
            ipt = {**self.default_inputs}
            self.set_input(ipt, 'arvalid', ar_valid)
            self.set_input(ipt, 'araddr', ar_addr)
            self.set_input(ipt, 'awvalid', aw_valid)
            self.set_input(ipt, 'awaddr', aw_addr)
            self.set_input(ipt, 'wvalid', w_valid)
            self.set_input(ipt, 'wdata', w_data)
            self.set_input(ipt, 'rready', r_ready)
            self.set_input(ipt, 'bready', b_ready)
            self.dut.set_inputs(ipt)
            logger.debug('End of cycle')
            await event.NextCycleFuture()
            opt = self.dut.get_outputs() 
            ar_ready = self.get_output(opt, 'arready')
            aw_ready = self.get_output(opt, 'awready')
            w_ready = self.get_output(opt, 'wready')
            b_valid = self.get_output(opt, 'bvalid')
            b_resp = self.get_output(opt, 'bresp')
            r_valid = self.get_output(opt, 'rvalid')
            r_resp = self.get_output(opt, 'rresp')
            r_data = self.get_output(opt, 'rdata')
            if (r_valid == 1) and (r_ready == 1):
                read_future = self.read_futures.popleft()
                rresp = self.get_output(opt, 'rresp')
                rdata = self.get_output(opt, 'rdata')
                if rresp == comms.OKAY:
                    read_future.set_result(rdata)
                else:
                    read_future.set_exception(ReadException(rresp, rdata))
            if (b_valid == 1) and (b_ready == 1):
                write_future = self.write_futures.popleft()
                bresp = self.get_output(opt, 'bresp')
                if bresp == comms.OKAY:
                    write_future.set_result(None)
                else:
                    write_future.set_exception(WriteException(bresp))
        self.active = False


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
