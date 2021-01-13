import logging
import random
from collections import deque, namedtuple

from slvcodec import cocotb_wrapper as cocotb
from slvcodec.cocotb_wrapper import triggers
from slvcodec import cocotb_helper

from axilent import comms


logger = logging.getLogger(__name__)


def signal_to_integer(s):
    if not s.value.is_resolvable:
        return None
    else:
        return s.value.integer


def make_axi_signals_from_prefixs(dut, m2s_prefix, s2m_prefix):
    axi_signals = {
        'awvalid': getattr(dut, m2s_prefix + 'awvalid'),
        'awaddr': getattr(dut, m2s_prefix + 'awaddr'),
        'awready': getattr(dut, s2m_prefix + 'awready'),
        'wvalid': getattr(dut, m2s_prefix + 'wvalid'),
        'wdata': getattr(dut, m2s_prefix + 'wdata'),
        'wready': getattr(dut, s2m_prefix + 'wready'),
        'bvalid': getattr(dut, s2m_prefix + 'bvalid'),
        'bresp': getattr(dut, s2m_prefix + 'bresp'),
        'bready': getattr(dut, m2s_prefix + 'bready'),
        'arvalid': getattr(dut, m2s_prefix + 'arvalid'),
        'araddr': getattr(dut, m2s_prefix + 'araddr'),
        'arready': getattr(dut, s2m_prefix + 'arready'),
        'rvalid': getattr(dut, s2m_prefix + 'rvalid'),
        'rresp': getattr(dut, s2m_prefix + 'rresp'),
        'rdata': getattr(dut, s2m_prefix + 'rdata'),
        'rready': getattr(dut, m2s_prefix + 'rready'),
        }
    return axi_signals


def make_axi_signals_from_interfaces(m2s, s2m):
    axi_signals = {
        'awvalid': m2s.awvalid,
        'awaddr': m2s.awaddr,
        'awready': s2m.awready,
        'wvalid': m2s.wvalid,
        'wdata': m2s.wdata,
        'wready': s2m.wready,
        'bvalid': s2m.bvalid,
        'bresp': s2m.bresp,
        'bready': m2s.bready,
        'arvalid': m2s.arvalid,
        'araddr': m2s.araddr,
        'arready': s2m.arready,
        'rvalid': s2m.rvalid,
        'rresp': s2m.rresp,
        'rdata': s2m.rdata,
        'rready': m2s.rready,
        }
    return axi_signals


QueueInfo = namedtuple('QueueInfo', ['throttle'])


class CocotbHandler(object):
    '''
    This handler receives `Command` objects and sends their AXI
    commands into a cocotb simulation.
    '''

    def __init__(self, clock_signal, axi_signals=None,
                 dut=None, m2s_prefix=None, s2m_prefix=None,
                 m2s=None, s2m=None, random_seed=None, helper=None):
        '''
        Args: 
          `clock_signal`: The signal for the clock.
          `axi_signals`: A dictionary relating signal names to the cocotb signal objects.
          `dut`, `m2s_prefix`, `s2m_prefix`: Alternately the axi signals can be constructed
             from the dut interface and the names of the prefixes for the m2s and s2m signals.
          `m2s`, `s2m`: Or the objects for the interfaces to the m2s and s2m signal bundles
             can be directly passed.
        '''
        if axi_signals is not None:
            assert m2s_prefix is None
            assert s2m_prefix is None
            assert m2s is None
            assert s2m is None
            self.signals = axi_signals
        elif m2s_prefix is not None:
            assert s2m_prefix is not None
            assert m2s is None
            assert s2m is None
            self.signals = make_axi_signals_from_prefixs(dut, m2s_prefix, s2m_prefix)
        else:
            assert m2s is not None
            assert s2m is not None
            assert s2m_prefix is None
            self.signals = make_axi_signals_from_interfaces(m2s, s2m)
        if helper is None:
            helper = cocotb_helper.TaskHelper()
        self.helper = helper
        self.clock_signal = clock_signal
        # Queues for storing 'w', 'aw', 'ar' commands until
        # they are sent into the simulation.
        self.w_queue = deque()
        self.aw_queue = deque()
        self.ar_queue = deque()
        # Queues for storing expectations of replies on the
        # 'b' and 'r' channels.
        self.b_queue = deque()
        self.r_queue = deque()
        self.command_queue = deque()
        self.random_seed = random_seed

    def start(self, aw_throttle=0.8, w_throttle=0.8, b_throttle=0.8,
              ar_throttle=0.8, r_throttle=0.8):
        """
        Activate the handler and start applying queued commands to the
        simulation.
        """
        self.helper.fork(self.process_queue_out(
            self.aw_queue,
            self.signals['awvalid'],
            self.signals['awready'],
            self.signals['awaddr'],
            QueueInfo(throttle=aw_throttle),
            random_seed=None if self.random_seed is None else self.random_seed + 10000,
        ))
        self.helper.fork(self.process_queue_out(
            self.w_queue,
            self.signals['wvalid'],
            self.signals['wready'],
            self.signals['wdata'],
            QueueInfo(throttle=w_throttle),
            random_seed=None if self.random_seed is None else self.random_seed + 20000,
        ))
        self.helper.fork(self.process_queue_in(
            self.b_queue,
            self.signals['bvalid'],
            self.signals['bready'],
            self.signals['bresp'],
            QueueInfo(throttle=b_throttle),
            random_seed=None if self.random_seed is None else self.random_seed + 30000,
        ))
        self.helper.fork(self.process_queue_out(
            self.ar_queue,
            self.signals['arvalid'],
            self.signals['arready'],
            self.signals['araddr'],
            QueueInfo(throttle=ar_throttle),
            random_seed=None if self.random_seed is None else self.random_seed + 40000,
        ))
        self.helper.fork(self.process_queue_in(
            self.r_queue,
            self.signals['rvalid'],
            self.signals['rready'],
            self.signals['rresp'],
            QueueInfo(throttle=r_throttle),
            self.signals['rdata'],
            random_seed=None if self.random_seed is None else self.random_seed + 50000,
        ))

    async def send(self, command):
        '''
        Sends a Command objects to the simulation and processes the responses.
        '''
        read_events = []
        write_events = []
        for ac in command.get_axi_commands():
            if isinstance(ac, comms.FakeWaitCommand):
                for dummy_index in range(ac.clock_cycles):
                    await self.helper.RisingEdge(self.clock_signal)
            else:
                assert(ac.readorwrite in (comms.WRITE_TYPE, comms.READ_TYPE))
                if ac.readorwrite == comms.WRITE_TYPE:
                    for offset, d in enumerate(ac.data):
                        address = ac.start_address
                        if not ac.constant_address:
                            if ac.address_by_word:
                                address += offset
                            else:
                                address += offset * 4
                        write_events.append(self.submit_write(address, d))
                else:
                    for index in range(ac.length):
                        address = ac.start_address
                        if not ac.constant_address:
                            if ac.address_by_word:
                                address += index
                            else:
                                address += index * 4
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

    async def read(self, address):
        event = self.submit_read(address)
        await event.wait()
        response, data = event.data
        if response != comms.OKAY:
            raise comms.AxiResponseException('Bad response: {}'.format(response))
        return data

    @cocotb_helper.killable
    async def process_queue_out(helper, self, queue, valid_signal, ready_signal, data_signal, queue_info,
                                random_seed=None):
        """
        Send data from a queue into the simulation using valid/ready hand shaking.
        """
        rnd = random if random_seed is None else random.Random(random_seed)
        while True:
            if queue:
                value = queue.popleft()
                while True:
                    valid = 1 if rnd.random() < queue_info.throttle else 0
                    valid_signal <= valid
                    if valid:
                        data_signal <= value
                    await helper.ReadOnly()
                    assert str(ready_signal) in ('0', '1')
                    consumed = (ready_signal == 1) and valid
                    await helper.RisingEdge(self.clock_signal)
                    if consumed:
                        break
            else:
                valid_signal <= 0
                await helper.RisingEdge(self.clock_signal)

    @cocotb_helper.killable
    async def process_queue_in(helper, self, queue, valid_signal, ready_signal, resp_signal, queue_info,
                               data_signal=None, random_seed=None):
        """
        Take data from the simulation using valid/ready shaking.
        Take an 'Event' from a queue and apply the received data to that event.
        """
        rnd = random if random_seed is None else random.Random(random_seed)
        while True:
            ready = 1 if rnd.random() < queue_info.throttle else 0
            ready_signal <= ready
            await helper.ReadOnly()
            assert str(valid_signal) in ('0', '1')
            if (valid_signal == 1) and ready:
                event = queue.popleft()
                if data_signal is not None:
                    event.set((resp_signal.value, data_signal.value))
                else:
                    event.set((resp_signal.value, None))
            await helper.RisingEdge(self.clock_signal)
