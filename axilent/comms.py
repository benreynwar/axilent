'''
Python tools for creating and parsing AXI communications.
'''

import logging
from collections import namedtuple

logger = logging.getLogger(__name__)

# `Comm` objects are registered here by the name of the module they are
# responsible for communicating with.
module_register = {}

# Response code for AXI.
OKAY = 0
EXOKAY = 1
SLVERR = 2
DECERR = 3


# Used to define whether AXI command are reading or writing.
READ_TYPE = 'READ'
WRITE_TYPE = 'WRITE'


AxiResponse = namedtuple('AxiResponse', ['length', 'data', 'resp'])


class AxiResponseException(Exception):
    pass


class Future:

    UNRESOLVED = 'unresolved'
    OKAY = 'okay'
    ERROR = 'error'

    def __init__(self):
        self.result_value = None
        self.exception_value = None
        self.state = self.UNRESOLVED

    def set_result(self, result):
        assert self.state == self.UNRESOLVED
        self.result_value = result
        self.state = self.OKAY

    def set_exception(self, exception):
        assert self.state == self.UNRESOLVED
        self.exception_value = exception
        self.state = self.ERROR

    def result(self):
        if self.state == self.ERROR:
            raise self.exception_value
        elif self.state == self.UNRESOLVED:
            raise Exception('Future is unresolved')
        else:
            return self.result_value


class Command(object):

    def __init__(self, description):
        self.description = description
        self.future = Future()

    def get_axi_commands(self):
        raise Exception('Unimplemented')

    def resolve_future(self, e, result):
        if e is not None:
            self.future.set_exception(e)
        else:
            if e is not None:
                self.future.set_exception(e)
            else:
                self.future.set_result(result)

    def process_responses(self, read_responses, write_responses, resolve_future=True):
        e, r = None, None
        if resolve_future:
            self.resolve_future(e, r)
        return e, r


WORD_SIZE = 4


class AxiCommand(Command):
    '''
    Defines a series AXI4Lite master-to-slave commands.
    '''

    def __init__(self, start_address, length, readorwrite, data=None,
                 constant_address=False, description=None, address_by_word=True):
        '''
        `start_address`: The address on which the first AXI command operates.
        `constant_address`: If this is `True` we keep operating on the same
             address, otherwise we increment.
        `length`: The number of commands.
        `readorwrite`: Can be either `READ_TYPE` or `WRITE_TYPE`.
        'data': A list of integers to send (if it is a write command).
        `description`: An optional description for debugging purposes.
        '''
        max_address = pow(2, 32)-1
        self.start_address = start_address
        self.length = length
        self.readorwrite = readorwrite
        self.constant_address = constant_address
        self.address_by_word = address_by_word
        assert readorwrite in (READ_TYPE, WRITE_TYPE)
        self.data = data
        if readorwrite == READ_TYPE:
            assert self.data is None
        else:
            assert len(self.data) == length
        assert start_address <= max_address
        if not constant_address:
            if address_by_word:
                assert start_address + length-1 <= max_address
            else:
                assert start_address + (length-1) * WORD_SIZE <= max_address
        assert description
        super().__init__(description)

    def get_axi_commands(self):
        return [self]

    def process_responses(self, read_responses, write_responses,
                          resolve_future=True):
        """
        Arguments:
          `read_responses`: An iterable of responses to read requests.  The
            iterable must begin with the requests to this command, which will
            be removed during processing.
          `write_responses`: An iterable of responses to write requests.  The
            iterable must begin with the requests to this command, which will
            be removed during processing.
          `resolve_future`: Whether the commands result future should be
            resolved.  This should be False when this command is getting
            wrapped by a higher level command.
        """
        relevant_responses = {
            READ_TYPE: read_responses,
            WRITE_TYPE: write_responses,
            }[self.readorwrite]
        data = []
        total_response_length = 0
        e = None
        while total_response_length < self.length:
            if not relevant_responses:
                e = Exception('Ran out of responses')
                break
            else:
                response = relevant_responses.popleft()
                total_response_length += response.length
                data += response.data
                if total_response_length > self.length:
                    e = Exception(
                        'Response lengths not matching command lengths')
                elif response.resp != OKAY:
                    e = AxiResponseException(
                        'Bad response in "{}"'.format(self.description))
        # Trim data down to right size.
        # Do this so that incorrect size does not trigger errors that hide
        # the real problem.
        data = data[:self.length]
        assert len(data) == self.length
        if resolve_future:
            self.resolve_future(e, data)
        return (e, data)


class SetUnsignedsCommand(AxiCommand):

    def __init__(self, values, address, description=None,
                 constant_address=False, address_by_word=True):
        for value in values:
            assert value < pow(2, 32)
        super().__init__(
            start_address=address,
            length=len(values),
            readorwrite=WRITE_TYPE,
            data=values,
            constant_address=constant_address,
            address_by_word=address_by_word,
            description=description,
        )


class SetUnsignedCommand(SetUnsignedsCommand):

    def __init__(self, value, address, description=None):
        super().__init__(
            address=address,
            values=[value],
            constant_address=True,
            description=description,
        )


class SetSignedsCommand(SetUnsignedsCommand):

    def __init__(self, values, address, description=None,
                 constant_address=False):
        offset = pow(2, 32)
        unsigneds = [v+offset if v < 0 else v for v in values]
        super().__init__(
            values=unsigneds,
            address=address,
            constant_address=constant_address,
            description=description,
        )


class SetSignedCommand(SetSignedsCommand):

    def __init__(self, value, address, description=None):
        super().__init__(
            address=address,
            values=[value],
            constant_address=True,
            description=description,
        )


class GetUnsignedsCommand(AxiCommand):

    def __init__(self, address, length=1, constant_address=False,
                 description=None):
        super().__init__(
            start_address=address,
            length=length,
            readorwrite=READ_TYPE,
            constant_address=constant_address,
            description=description,
        )


class GetUnsignedCommand(AxiCommand):

    def __init__(self, address, description=None):
        super().__init__(
            start_address=address,
            length=1,
            readorwrite=READ_TYPE,
            constant_address=True,
            description=description,
        )

    def process_responses(self, read_responses, write_responses,
                          resolve_future=True):
        e, result = super().process_responses(read_responses, write_responses,
                                              resolve_future=False)
        assert len(result) == 1
        if resolve_future:
            self.resolve_future(e, result[0])
        return e, result[0]


class TriggerCommand(AxiCommand):

    def __init__(self, address, description):
        super().__init__(
            start_address=address,
            data=[0],
            length=1,
            readorwrite=WRITE_TYPE,
            constant_address=True,
            description=description,
            )


class GetBooleanCommand(AxiCommand):

    def __init__(self, address, description=None):
        super().__init__(
            start_address=address,
            length=1,
            readorwrite=READ_TYPE,
            constant_address=True,
            description=description,
        )

    def process_responses(self, read_responses, write_responses,
                          resolve_future=True):
        e, result = super().process_responses(read_responses, write_responses,
                                              resolve_future=False)
        r = None
        if not e:
            if len(result) != 1:
                e = Exception('Wrong number of results')
            else:
                first_result = result[0]
                if first_result == 1:
                    r = True
                elif first_result == 0:
                    r = False
                else:
                    msg = 'Return value must be 0 to 1 for boolean.  Is {}.'
                    e = Exception(msg.format(result))
        if resolve_future:
            self.resolve_future(e, r)
        return (e, r)


class SetBooleanCommand(AxiCommand):

    def __init__(self, value, address, description=None):
        if value:
            b = 1
        else:
            b = 0
        super().__init__(
            start_address=address,
            data=[b],
            length=1,
            readorwrite=WRITE_TYPE,
            constant_address=True,
            description=description,
        )


class FakeWaitCommand:
    '''
    This is used when we're sending commands to a simulation.
    The `DictCommandHandler` translates it into a bunch of empty
    master-to-slave dictionaries.
    It can be also used when communicating with an FPGA to indicate
    a sleep time.  This is for compatibility of tests.
    '''

    def __init__(self, clock_cycles, sleep_time=0, description=None):
        self.clock_cycles = clock_cycles
        self.axi_commands = []
        self.sleep_time = sleep_time
        self.length = 1
        if description is None:
            self.description = 'Fake wait for {} clock cycles / {} time'.format(
                clock_cycles, sleep_time)
        else:
            self.description = description

    def process_responses(self, read_responses, write_responses,
                          resolve_future=False):
        return None, None

    def get_axi_commands(self):
        return [self]


class CombinedCommand(Command):

    def __init__(self, commands, description):
        self.commands = commands
        super().__init__(description)

    def get_axi_commands(self):
        acs = []
        for command in self.commands:
            acs += command.get_axi_commands()
        return acs

    def process_responses(self, read_responses, write_responses,
                          resolve_future=True):
        first_e = None
        results = []
        for command in self.commands:
            e, result = command.process_responses(
                read_responses, write_responses)
            if (e is not None) and (first_e is None):
                first_e = e
            results.append(result)
        if resolve_future:
            self.resolve_future(first_e, None)
        return first_e, results
