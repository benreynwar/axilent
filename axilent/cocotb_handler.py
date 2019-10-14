import time
import logging
import asyncio
from collections import deque

import cocotb
from cocotb import log
from cocotb.triggers import Event, RisingEdge, FallingEdge, Timer
from slvcodec import cocotb_wrapper

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

    def __init__(self, clock_signal, clock_period, reset_signal, axi_signals, logger):
        '''
        `clock_signal`: The signal for the clock.
        `clock_period`: The period of the clock.
        `axi_signals`: A dictionary relating signal names to the cocotb signal objects.
        '''
        self.logger = logger
        self.clock_signal = clock_signal
        self.clock_period = clock_period
        self.reset_signal = reset_signal
        assert int(self.clock_period) >= 2
        self.clock_down = int(self.clock_period * 0.5)
        self.clock_up = int(self.clock_period) - self.clock_down
        self.signals = axi_signals
        self.write_request_queue = deque()
        self.read_request_queue = deque()
        self.write_response_queue = deque()
        self.read_response_queue = deque()
        self.command_queue = deque()

    @cocotb.coroutine
    async def start(self):
        cocotb.fork(self.clock())
        await RisingEdge(self.clock_signal)
        self.reset_signal <= 1
        await RisingEdge(self.clock_signal)
        self.reset_signal <= 0
        cocotb.fork(self.process_write_requests())
        cocotb.fork(self.process_write_responses())
        cocotb.fork(self.process_read_requests())
        cocotb.fork(self.process_read_responses())

    def send(self, command):
        log.info('queuing command {}'.format(command.description))
        self.command_queue.append(command)

    @cocotb.coroutine
    async def send_stored_commands(self):
        while self.command_queue:
            command = self.command_queue.popleft()
            log.info('sending command {}'.format(command.description))
            await self.send_single_command(command)

    @cocotb.coroutine
    async def send_single_command(self, command):
        '''
        Sends a Command objects to the FPGA and processes the responses.
        '''
        log.info('really sending command {}'.format(command.description))
        read_events = []
        write_events = []
        for ac in command.get_axi_commands():
            log.debug('Command sent for %s.', ac.description)
            if isinstance(ac, comms.FakeWaitCommand):
                log.info('Waiting for {} clock cycles'.format(ac.clock_cycles))
                for dummy_index in range(ac.clock_cycles):
                    await RisingEdge(self.clock_signal)
                    if dummy_index % 10 == 0:
                        log.info('Got clock cycles {}/{}'.format(dummy_index, ac.clock_cycles))
            else:
                assert(ac.readorwrite in (comms.WRITE_TYPE, comms.READ_TYPE))
                if ac.readorwrite == comms.WRITE_TYPE:
                    for offset, d in enumerate(ac.data):
                        address = ac.start_address
                        if not ac.constant_address:
                            address += offset
                        write_events.append(self.write(address, d, add_trigger=True))
                else:
                    for index in range(ac.length):
                        address = ac.start_address
                        if not ac.constant_address:
                            address += index
                        read_events.append(self.read(address, add_trigger=True))
        log.info('Finished sending')

        log.info('{} read events and {} write_events'.format(len(read_events), len(write_events)))
        for index, event in enumerate(write_events):
            log.info('Waiting for write event {}'.format(index))
            await event.wait()
            log.info('Got write event {}'.format(index))
        for index, event in enumerate(read_events):
            log.info('Waiting for read event {}'.format(index))
            await event.wait()
            log.info('Got read event {}'.format(index))
        write_event_results = [f.result() for f in write_events]
        write_responses = [comms.AxiResponse(length=1, data=[None], resp=resp)
                           for resp in write_event_results]

        read_event_results = [f.result() for f in read_events]
        read_responses = [comms.AxiResponse(length=1, data=[data], resp=resp)
                          for resp, data in read_event_results]
        log.info('Got response')
        command.process_responses(read_responses, write_responses)
        log.info('Finished processing')

    @cocotb.coroutine
    async def write(self, address, value, add_trigger=True):
        event = cocotb_wrapper.Event()
        self.write_request_queue.append((address, value, event))
        await event.wait()
        response = event.data
        if response != comms.OKAY:
            raise comms.AxiResponseException('Bad response: {}'.format(response))

    @cocotb.coroutine
    async def read(self, address, add_trigger=True):
        event = cocotb_wrapper.Event()
        self.read_request_queue.append((address, event))
        await event.wait()
        response, data = event.data
        if response != comms.OKAY:
            raise comms.AxiResponseException('Bad response: {}'.format(response))
        return data

    @cocotb.coroutine
    async def clock(self):
        while True:
            self.clock_signal <= 0
            await Timer(self.clock_down)
            self.clock_signal <= 1
            await Timer(self.clock_up)

    @cocotb.coroutine
    async def process_write_requests(self):
        self.logger.info('process write requests')
        while True:
            await RisingEdge(self.clock_signal)
            await Timer(int(self.clock_period*0.1))
            if self.write_request_queue:
                address, value, event = self.write_request_queue.popleft()
                self.signals['wvalid'].setimmediatevalue(1)
                self.signals['wdata'].setimmediatevalue(value)
                self.signals['awvalid'].setimmediatevalue(1)
                self.signals['awaddr'].setimmediatevalue(address)
                sent_w = False
                sent_aw = False
                while True:
                    await FallingEdge(self.clock_signal)
                    await Timer(int(self.clock_period * 0.4))
                    if not sent_w:
                        sent_w = (self.signals['wready'] == 1)
                    if not sent_aw:
                        sent_aw = (self.signals['awready'] == 1)
                    if sent_w and sent_aw:
                        self.write_response_queue.append(event)
                        break
                    await RisingEdge(self.clock_signal)
                    await Timer(int(self.clock_period * 0.1))
                    if sent_aw:
                        self.signals['awvalid'].setimmediatevalue(0)
                    if sent_w:
                        self.signals['wvalid'].setimmediatevalue(0)
            else:
                self.signals['awvalid'].setimmediatevalue(0)
                self.signals['wvalid'].setimmediatevalue(0)

    @cocotb.coroutine
    async def process_write_responses(self):
        self.logger.info('process write responses')
        self.signals['bready'].setimmediatevalue(1)
        while True:
            await FallingEdge(self.clock_signal)
            await Timer(int(self.clock_period * 0.4))
            if self.signals['bvalid'] == 1:
                response = self.signals['bresp'].value.integer
                event = self.write_response_queue.popleft()
                event.set(response)

    @cocotb.coroutine
    async def process_read_requests(self):
        self.logger.info('process read requests')
        while True:
            await RisingEdge(self.clock_signal)
            await Timer(int(self.clock_period * 0.1))
            if self.read_request_queue:
                address, event = self.read_request_queue.popleft()
                self.signals['arvalid'].setimmediatevalue(1)
                self.signals['araddr'].setimmediatevalue(address)
                sent_ar = False
                while True:
                    await FallingEdge(self.clock_signal)
                    await Timer(int(self.clock_period * 0.4))
                    if not sent_ar:
                        sent_ar = (self.signals['arready'].value == 1)
                    if sent_ar:
                        self.read_response_queue.append(event)
                        break
                    await RisingEdge(self.clock_signal)
                    await Timer(int(self.clock_period * 0.1))
            else:
                self.signals['arvalid'].setimmediatevalue(0)

    @cocotb.coroutine
    async def process_read_responses(self):
        self.logger.info('process read responses')
        self.signals['rready'].setimmediatevalue(1)
        while True:
            await FallingEdge(self.clock_signal)
            await Timer(int(self.clock_period * 0.4))
            if self.signals['rvalid'] == 1:
                response = self.signals['rresp'].value.integer
                data = signal_to_integer(self.signals['rdata'])
                event = self.read_response_queue.popleft()
                event.set((response, data))
