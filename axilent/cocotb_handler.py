import logging
from collections import deque

from slvcodec import cocotb_wrapper as cocotb
from slvcodec.cocotb_wrapper import triggers

from axilent import comms


logger = logging.getLogger(__name__)


def signal_to_integer(s):
    if not s.value.is_resolvable:
        return None
    else:
        return s.value.integer
    

class CocotbHandler(object):
    '''
    This handler receives `Command` objects and sends their AXI
    commands into a cocotb simulation.
    '''

    def __init__(self, clock_signal, axi_signals):
        '''
        `clock_signal`: The signal for the clock.
        `axi_signals`: A dictionary relating signal names to the cocotb signal objects.
        '''
        self.clock_signal = clock_signal
        self.signals = axi_signals
        self.w_queue = deque()
        self.aw_queue = deque()
        self.b_queue = deque()
        self.ar_queue = deque()
        self.r_queue = deque()
        self.command_queue = deque()

    def start(self):
        cocotb.fork(self.process_queue_out(
            self.aw_queue,
            self.signals['awvalid'],
            self.signals['awready'],
            self.signals['awaddr'],
        ))
        cocotb.fork(self.process_queue_out(
            self.w_queue,
            self.signals['wvalid'],
            self.signals['wready'],
            self.signals['wdata'],
        ))
        cocotb.fork(self.process_queue_in(
            self.b_queue,
            self.signals['bvalid'],
            self.signals['bready'],
            self.signals['bresp'],
        ))
        cocotb.fork(self.process_queue_out(
            self.ar_queue,
            self.signals['arvalid'],
            self.signals['arready'],
            self.signals['araddr'],
        ))
        cocotb.fork(self.process_queue_in(
            self.r_queue,
            self.signals['rvalid'],
            self.signals['rready'],
            self.signals['rresp'],
            self.signals['rdata'],
        ))

    def send(self, command):
        self.command_queue.append(command)

    @cocotb.coroutine
    async def send_stored_commands(self):
        while self.command_queue:
            command = self.command_queue.popleft()
            await self.send_single_command(command)

    @cocotb.coroutine
    async def send_single_command(self, command):
        '''
        Sends a Command objects to the FPGA and processes the responses.
        '''
        read_events = []
        write_events = []
        for ac in command.get_axi_commands():
            if isinstance(ac, comms.FakeWaitCommand):
                for dummy_index in range(ac.clock_cycles):
                    await triggers.RisingEdge(self.clock_signal)
            else:
                assert(ac.readorwrite in (comms.WRITE_TYPE, comms.READ_TYPE))
                if ac.readorwrite == comms.WRITE_TYPE:
                    for offset, d in enumerate(ac.data):
                        address = ac.start_address
                        if not ac.constant_address:
                            address += offset
                        write_events.append(self.submit_write(address, d))
                else:
                    for index in range(ac.length):
                        address = ac.start_address
                        if not ac.constant_address:
                            address += index
                        read_events.append(self.submit_read(address))

        for index, event in enumerate(write_events):
            await event.wait()
        for index, event in enumerate(read_events):
            await event.wait()
        write_event_results = [f.data for f in write_events]
        write_responses = deque(comms.AxiResponse(length=1, data=[None if data is None else int(data)], resp=resp)
                           for resp, data in write_event_results)

        read_event_results = [f.data for f in read_events]
        read_responses = deque(comms.AxiResponse(length=1, data=[None if data is None else int(data)], resp=resp)
                          for resp, data in read_event_results)
        command.process_responses(read_responses, write_responses)
        return command.future.result()

    def submit_write(self, address, value):
        event = triggers.Event()
        self.aw_queue.append(address)
        self.w_queue.append(value)
        self.b_queue.append(event)
        return event

    @cocotb.coroutine
    async def write(self, address, value):
        event = self.submit_write(address, value)
        await event.wait()
        response, data = event.data
        if response != comms.OKAY:
            raise comms.AxiResponseException('Bad response: {}'.format(response))
        return data

    def submit_read(self, address):
        event = triggers.Event()
        self.ar_queue.append(address)
        self.r_queue.append(event)
        return event

    @cocotb.coroutine
    async def read(self, address):
        event = self.submit_read(address)
        await event.wait()
        response, data = event.data
        if response != comms.OKAY:
            raise comms.AxiResponseException('Bad response: {}'.format(response))
        return data

    @cocotb.coroutine
    async def process_queue_out(self, queue, valid_signal, ready_signal, data_signal):
        while True:
            if queue:
                value = queue.popleft()
                valid_signal <= 1
                data_signal <= value
                while True:
                    await triggers.ReadOnly()
                    assert str(ready_signal) in ('0', '1')
                    consumed = ready_signal == 1
                    await triggers.RisingEdge(self.clock_signal)
                    if consumed:
                        break
            else:
                valid_signal <= 0
                await triggers.RisingEdge(self.clock_signal)

    @cocotb.coroutine
    async def process_queue_in(self, queue, valid_signal, ready_signal, resp_signal, data_signal=None):
        ready_signal <= 1
        while True:
            await triggers.ReadOnly()
            if str(valid_signal) not in ('0', '1'):
                import pdb
                pdb.set_trace()
            assert str(valid_signal) in ('0', '1')
            if valid_signal == 1:
                event = queue.popleft()
                if data_signal is not None:
                    event.set((resp_signal.value, data_signal.value))
                else:
                    event.set((resp_signal.value, None))
            await triggers.RisingEdge(self.clock_signal)
