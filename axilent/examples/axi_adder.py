import logging
import random

from slvcodec.test_utils import WrapperTest
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
