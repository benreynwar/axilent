import logging
import random

from slvcodec import fusesoc_wrapper
from slvcodec import cocotb_wrapper as cocotb

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

    @cocotb.coroutine
    async def add_numbers_async(self, a, b):
        write_a_and_b_command = comms.CombinedCommand((
            comms.SetUnsignedCommand(
                address=self.addresses['intA'], value=a,
                description='Setting A in AddNumbers',
            ),
            comms.SetUnsignedCommand(
                address=self.addresses['intB'], value=b,
                description='Setting B in AddNumbers',
            ),
            ), description='Setting A and B in AddNumbers')
        await self.handler.send(write_a_and_b_command)
        read_c_command = comms.GetUnsignedCommand(
            address=self.addresses['intC'],
            description='Getting C from AddNumbers',
        )
        result = await self.handler.send(read_c_command)
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

