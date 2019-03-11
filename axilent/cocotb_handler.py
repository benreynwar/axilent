import time
import logging
import asyncio

import cocotb
from cocotb import log
from cocotb.triggers import Event, RisingEdge, FallingEdge, Timer

from collections import deque

from axilent import comms

def signal_to_integer(s):
    if not s.value.is_resolvable:
        log.error("Signal is not resolvable")
        import pdb
        pdb.set_trace()
        return None
    else:
        return s.value.integer
    

class CocotbHandler(object):
    '''
    This handler receives `Command` objects and sends their AXI
    commands into a cocotb simulation.
    '''

    def __init__(self, clock_signal, clock_period, axi_signals):
        '''
        `clock_signal`: The signal for the clock.
        `clock_period`: The period of the clock.
        `axi_signals`: A dictionary relating signal names to the cocotb signal objects.
        '''
        self.clock_signal = clock_signal
        self.clock_period = clock_period
        self.signals = axi_signals
        self.write_request_queue = deque()
        self.read_request_queue = deque()
        self.write_response_queue = deque()
        self.read_response_queue = deque()
        cocotb.fork(self.process_write_requests())
        cocotb.fork(self.process_write_responses())
        cocotb.fork(self.process_read_requests())
        cocotb.fork(self.process_read_responses())
        self.command_queue = deque()

    def send(self, command):
        log.info('queuing command {}'.format(command.description))
        self.command_queue.append(command)

    @cocotb.coroutine
    def send_stored_commands(self):
        while self.command_queue:
            command = self.command_queue.popleft()
            log.info('sending command {}'.format(command.description))
            yield self.send_single_command(command)

    @cocotb.coroutine
    def send_single_command(self, command):
        '''
        Sends a Command objects to the FPGA and processes the responses.
        '''
        log.info('really sending command {}'.format(command.description))
        read_futures = []
        write_futures = []
        for ac in command.get_axi_commands():
            log.debug('Command sent for %s.', ac.description)
            if isinstance(ac, comms.FakeWaitCommand):
                log.info('Waiting for {} clock cycles'.format(ac.clock_cycles))
                for dummy_index in range(ac.clock_cycles):
                    yield RisingEdge(self.clock_signal)
                    if dummy_index % 10 == 0:
                        log.info('Got clock cycles {}/{}'.format(dummy_index, ac.clock_cycles))
            else:
                assert(ac.readorwrite in (comms.WRITE_TYPE, comms.READ_TYPE))
                if ac.readorwrite == comms.WRITE_TYPE:
                    for offset, d in enumerate(ac.data):
                        address = ac.start_address
                        if not ac.constant_address:
                            address += offset
                        write_futures.append(self.write(address, d, add_trigger=True))
                else:
                    for index in range(ac.length):
                        address = ac.start_address
                        if not ac.constant_address:
                            address += index
                        read_futures.append(self.read(address, add_trigger=True))
        log.info('Finished sending')

        log.info('{} read futures and {} write_futures'.format(len(read_futures), len(write_futures)))
        for index, future in enumerate(write_futures):
            log.info('Waiting for write future {}'.format(index))
            yield future.trigger.wait()
            log.info('Got write future {}'.format(index))
        for index, future in enumerate(read_futures):
            log.info('Waiting for read future {}'.format(index))
            yield future.trigger.wait()
            log.info('Got read future {}'.format(index))
        write_future_results = [f.result() for f in write_futures]
        write_responses = [comms.AxiResponse(length=1, data=[None], resp=resp)
                           for resp in write_future_results]

        read_future_results = [f.result() for f in read_futures]
        read_responses = [comms.AxiResponse(length=1, data=[data], resp=resp)
                          for resp, data in read_future_results]
        log.info('Got response')
        command.process_responses(read_responses, write_responses)
        log.info('Finished processing')

    def write(self, address, value, add_trigger=True):
        future = asyncio.Future()
        self.write_request_queue.append((address, value, future))
        if add_trigger:
            future.trigger = Event()
        return future

    def read(self, address, add_trigger=True):
        future = asyncio.Future()
        self.read_request_queue.append((address, future))
        if add_trigger:
            future.trigger = Event()
        return future

    @cocotb.coroutine
    def process_write_requests(self):
        while True:
            yield RisingEdge(self.clock_signal)
            yield Timer(int(self.clock_period*0.1))
            if self.write_request_queue:
                address, value, future = self.write_request_queue.popleft()
                self.signals['wvalid'].setimmediatevalue(1)
                self.signals['wdata'].setimmediatevalue(value)
                self.signals['awvalid'].setimmediatevalue(1)
                self.signals['awaddr'].setimmediatevalue(address)
                sent_w = False
                sent_aw = False
                while True:
                    yield FallingEdge(self.clock_signal)
                    yield Timer(int(self.clock_period * 0.4))
                    if not sent_w:
                        sent_w = (self.signals['wready'] == 1)
                    if not sent_aw:
                        sent_aw = (self.signals['awready'] == 1)
                    if sent_w and sent_aw:
                        self.write_response_queue.append(future)
                        break
                    yield RisingEdge(self.clock_signal)
                    yield Timer(int(self.clock_period * 0.1))
                    if sent_aw:
                        self.signals['awvalid'].setimmediatevalue(0)
                    if sent_w:
                        self.signals['wvalid'].setimmediatevalue(0)
            else:
                self.signals['awvalid'].setimmediatevalue(0)
                self.signals['wvalid'].setimmediatevalue(0)

    @cocotb.coroutine
    def process_write_responses(self):
        self.signals['bready'].setimmediatevalue(1)
        while True:
            yield FallingEdge(self.clock_signal)
            yield Timer(int(self.clock_period * 0.4))
            if self.signals['bvalid'] == 1:
                response = self.signals['bresp'].value.integer
                future = self.write_response_queue.popleft()
                future.set_result(response)
                if hasattr(future, 'trigger'):
                    future.trigger.set()

    @cocotb.coroutine
    def process_read_requests(self):
        while True:
            yield RisingEdge(self.clock_signal)
            yield Timer(int(self.clock_period * 0.1))
            if self.read_request_queue:
                address, future = self.read_request_queue.popleft()
                self.signals['arvalid'].setimmediatevalue(1)
                self.signals['araddr'].setimmediatevalue(address)
                sent_ar = False
                while True:
                    yield FallingEdge(self.clock_signal)
                    yield Timer(int(self.clock_period * 0.4))
                    if not sent_ar:
                        sent_ar = (self.signals['arready'].value == 1)
                    if sent_ar:
                        self.read_response_queue.append(future)
                        break
                    yield RisingEdge(self.clock_signal)
                    yield Timer(int(self.clock_period * 0.1))
            else:
                self.signals['arvalid'].setimmediatevalue(0)

    @cocotb.coroutine
    def process_read_responses(self):
        self.signals['rready'].setimmediatevalue(1)
        while True:
            yield FallingEdge(self.clock_signal)
            yield Timer(int(self.clock_period * 0.4))
            if self.signals['rvalid'] == 1:
                response = self.signals['rresp'].value.integer
                data = signal_to_integer(self.signals['rdata'])
                future = self.read_response_queue.popleft()
                future.set_result((response, data))
                if hasattr(future, 'trigger'):
                    future.trigger.set()
