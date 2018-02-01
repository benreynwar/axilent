import random
import logging

from axilent import handlers, dicts


logger = logging.getLogger(__name__)


class DictAxiTest(object):
    '''
    Wraps a test with prepare and check methods with a test that
    exposes make_input_data and check_output_data methods.
    '''

    def __init__(self, axi_test, terminate_early=False):
        self.axi_test = axi_test
        self.handler = handlers.DictCommandHandler()
        self.terminate_early = terminate_early

    def make_input_data(self):
        input_data = [{
            'reset': 1,
            'm2s': dicts.make_empty_axi4lite_m2s_dict(),
        }]
        self.axi_test.prepare(self.handler)
        m2s = self.handler.make_command_dicts()
        input_data += [{
            'reset': 0,
            'm2s': d,
            } for d in m2s]
        if self.terminate_early:
            input_data = input_data[:random.randint(1, len(input_data))]
        return input_data

    def check_output_data(self, input_data, output_data):
        if not self.terminate_early:
            response_dicts = [d['s2m'] for d in output_data[1:]]
            self.handler.consume_response_dicts(response_dicts)
            self.axi_test.check()
