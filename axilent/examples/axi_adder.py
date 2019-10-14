import logging
import random

from slvcodec.test_utils import WrapperTest
from slvcodec import event, fusesoc_wrapper, cocotb_wrapper

from axilent.test_utils import DictAxiTest
from axilent import comms


logger = logging.getLogger(__name__)


class AxiAdderComm(object):
    '''
    Class to communicate with the AxiAdder module.
    '''

    INTA_ADDRESS = 0
    INTB_ADDRESS = 1
    INTC_ADDRESS = 2

    def __init__(self, address_offset, handler):
        '''
        `address_offset` is any addition that is made to the address that is
        consumed during routing.
        `handler` is the object responsible for dispatching the commands.
        '''
        self.handler = handler
        self.address_offset = address_offset
        self.addresses = {
            'intA': address_offset + self.INTA_ADDRESS,
            'intB': address_offset + self.INTB_ADDRESS,
            'intC': address_offset + self.INTC_ADDRESS,
        }

    def add_numbers(self, a, b):
        '''
        A complex complex command that write to two registers and
        then reads from another.
        Sets 'a' and 'b' then reads 'c' (should be a+b)
        '''
        command = AddNumbersCommand(a, b, self.addresses)
        self.handler.send(command)
        return command.future

    @cocotb_wrapper.coroutine
    async def async_add_numbers(self, a, b):
        logger.debug('Doing writes')
        await cocotb_wrapper.Combine(
            self.handler.write(address=self.addresses['intA'], value=a),
            self.handler.write(address=self.addresses['intB'], value=b),
            )
        logger.debug('Doing read')
        result = await self.handler.read(address=self.addresses['intC'])
        logger.debug('Got result')
        return result


class AddNumbersCommand(comms.CombinedCommand):
    '''
    A command that writes to the intA and intB registers
    and then reads from the intC register.
    The effect is the add the two inputs.
    '''

    def __init__(self, a, b, addresses):
        write_a_command = comms.SetUnsignedCommand(
            address=addresses['intA'], value=a,
            description='Setting A in AddNumbers',
        )
        write_b_command = comms.SetUnsignedCommand(
            address=addresses['intB'], value=b,
            description='Setting B in AddNumbers',
        )
        read_c_command = comms.GetUnsignedCommand(
            address=addresses['intC'],
            description='Getting C from AddNumbers',
        )
        commands = (write_a_command, write_b_command, read_c_command)
        super().__init__(
            description='Add 2 numbers with AddNumber',
            commands=commands)

    def process_responses(self, read_responses, write_responses, resolve_future=True):
        '''
        Return the third response (from the final read command)
        Don't return any errors.
        '''
        e, result = super().process_responses(read_responses, write_responses, resolve_future=False)
        intc = result[2]
        if resolve_future:
            self.resolve_future(e, intc)
        return e, intc


class AxiAdderTest(object):
    """
    This is a test with the restriction that all the inputs must be specified before any
    out of the outputs are received.
    """

    def __init__(self):
        self.expected_intcs = []
        self.intc_futures = []

    def prepare(self, handler):
        '''
        Sends a number of 'add_numbers' commands.
        '''
        comm = AxiAdderComm(address_offset=0, handler=handler)
        n_data = 20
        max_int = pow(2, 16)-1
        logger.debug('preparing data')
        for i in range(n_data):
            inta = random.randint(0, max_int)
            intb = random.randint(0, max_int)
            self.expected_intcs.append(inta + intb)
            future = comm.add_numbers(inta, intb)
            self.intc_futures.append(future)
        # Flush the communication for simulations.
        # Ignored in FPGA.
        handler.send(comms.FakeWaitCommand(clock_cycles=10))

    def check(self):
        '''
        Check that the output of the commands matches the expected values.
        '''
        output_intcs = [f.result() for f in self.intc_futures]
        assert output_intcs == self.expected_intcs
        print('Success!!!!!!!!!!!!!!!')


async def axi_adder_test(dut, handler):
    comm = AxiAdderComm(address_offset=0, handler=handler)
    n_data = 100
    max_int = pow(2, 16)-1
    logger.debug('preparing data')
    for i in range(n_data):
        inta = random.randint(0, max_int)
        intb = random.randint(0, max_int)
        intc = await comm.async_add_numbers(inta, intb)
        assert intc == inta + intb
        logger.debug('{} matched'.format(i))
    cocotb_wrapper.terminate()


async def axi_adder_assertions_test(dut):
    dut.reset = 1
    await event.NextCycleFuture()
    dut.reset = 0
    dut.m2s.awvalid = 1
    dut.s2m.awready = 1
    dut.m2s.wvalid = 1
    dut.s2m.wready = 1
    dut.s2m.bvalid = 0
    dut.m2s.bready = 0
    dut.m2s.arvalid = 0
    dut.s2m.arready = 0
    dut.s2m.rvalid = 0
    dut.m2s.rready = 0
    await event.NextCycleFuture()
    print(dut.get())
    dut.m2s.awvalid = 0
    dut.s2m.awready = 0
    dut.m2s.wvalid = 0
    dut.s2m.wready = 0
    dut.s2m.bvalid = 1
    dut.m2s.bready = 1
    dut.m2s.rready = 1
    await event.NextCycleFuture()
    print(dut.get())
    await event.NextCycleFuture()
    print(dut.get())
    dut.s2m.bvalid = 0
    for i in range(200):
        await event.NextCycleFuture()
        print(dut.get())
    #assert dut.assertions.output.w_mismatch == 1
    raise event.TerminateException()


def make_test(entity, generics, top_params):
    tests = []
    for test_index in range(20):
        terminate_early = random.choice([True, False])
        axi_test = AxiAdderTest()
        tests.append(DictAxiTest(axi_test, terminate_early))
    combined_test = WrapperTest(tests)
    return combined_test


def get_tests():
    test = {
        'core_name': 'axi_adder',
        'entity_name': 'axi_adder',
        'param_sets': [{
            'generic_sets': [{}],
            'top_params': {}
        }],
        'generator': make_test,
        }
    return [test]

def convert_to_verilog():
    working_directory = 'deleteme_axi_adder'
    core_name = 'axi_adder'
    parameters = {}
    config_filename = '/home/ben/Code/axilent/axilent/fusesoc.conf'
    filenames = fusesoc_wrapper.generate_core(
        working_directory, core_name, parameters, config_filename=config_filename, tool='vivado')
    print(filenames)
    import subprocess
    for filename in filenames:
        subprocess.call(['ghdl', '-a', filename])
    subprocess.call(['yosys', '-m', 'ghdl', '-p', 'ghdl axi_adder; write_verilog axi_adder.v'])


if __name__ == '__main__':
    convert_to_verilog()
