import random
import logging

from axilent import handlers, dicts


logger = logging.getLogger(__name__)


class DictAxiTest(object):
    '''
    Wraps a test with prepare and check methods with a test that
    exposes make_input_data and check_output_data methods.
    '''

    def __init__(self, axi_test, terminate_early=False, clock_names=None, reset=True,
                 m2s_name='m2s', s2m_name='s2m'):
        self.axi_test = axi_test
        self.handler = handlers.DictCommandHandler()
        self.terminate_early = terminate_early
        self.clock_names = clock_names
        self.reset = reset
        self.m2s_name = m2s_name
        self.s2m_name = s2m_name

    def make_input_data(self):
        input_data = []
        if self.reset:
            input_data.append({
                'reset': 1,
                self.m2s_name: dicts.make_empty_axi4lite_m2s_dict(),
            })
        self.axi_test.prepare(self.handler)
        m2s = self.handler.make_command_dicts()
        input_data += [{
            'reset': 0,
            self.m2s_name: d,
            } for d in m2s]
        if self.terminate_early:
            input_data = input_data[:random.randint(1, len(input_data))]
        if self.clock_names:
            input_data = {
                self.clock_names[0]: input_data,
                }
            for clock_name in self.clock_names[1:]:
                input_data[clock_name] = []

        return input_data

    def check_output_data(self, input_data, output_data):
        if self.clock_names:
            input_data = input_data[self.clock_names[0]]
            output_data = output_data[self.clock_names[0]]
        if not self.terminate_early:
            ds = [{**ipt[self.m2s_name], **opt[self.s2m_name]} for ipt, opt in zip(
                input_data[1:], output_data[1:])]
            self.handler.consume_response_dicts(ds)
            self.axi_test.check()


class CombinedHandlerTest:

    def __init__(self, subtests, handler):
        self.subtests = subtests
        self.handler = handler

    def make_input_data(self):
        input_data = []
        old_length = 0
        self.lengths = []
        for test in self.subtests:
            input_data += test.make_input_data()
            new_length = len(input_data)
            self.lengths.append((old_length, new_length))
            old_length = new_length
        return input_data

    def check_output_data(self, input_data, output_data):
        # Assume that we ignore the first output_data due to reset.
        reset_index = 0
        response_dicts = [
            {**ipt['config_m2s'], **opt['config_s2m']}
            for ipt, opt in zip(input_data[reset_index+1:], output_data[reset_index+1:])]
        self.handler.consume_response_dicts(response_dicts)
        n_subtests = len(self.subtests)
        for index, indices, test in zip(range(n_subtests), self.lengths, self.subtests):
            logger.debug('Checking output in subtest {}/{}'.format(index+1, n_subtests))
            start_index, end_index = indices
            sub_input_data = input_data[start_index: end_index]
            sub_output_data = output_data[start_index: end_index]
            test.check_output_data(sub_input_data, sub_output_data)
