import os
import logging

from slvcodec import config as slvcodec_config, test_utils
from axilent.examples import axi_adder
from axilent import coresdir, handlers, config

testoutput_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'test_outputs'))


logger = logging.getLogger(__name__)


def test_axi_adder():
    tests = axi_adder.get_tests()
    slvcodec_config.setup_fusesoc(cores_roots=[coresdir])
    vu = slvcodec_config.setup_vunit(argv=['--dont-catch-exceptions'])
    for coretest in tests:
        test_utils.register_coretest_with_vunit(vu, coretest, testoutput_dir)
    all_ok = vu._main(post_run=None)
    assert all_ok


def test_axi_adder_with_pipe():
    logger.debug('Starting test')
    tests = axi_adder.get_tests()
    handler = handlers.NamedPipeHandler('m2s', 's2m', generators=[axi_adder.axi_adder_pipe_test])
    directory = os.path.join(testoutput_dir, 'axi_adder_pipe')
    top_entity = 'axi_adder'
    filenames = [
        '/home/ben/Code/axilent/axilent/vhdl/axi_utils.vhd',
        '/home/ben/Code/axilent/axilent/vhdl/axi_adder.vhd',
        ]
    generics = {
        }
    test_generators = [handler.communicate]
    test_utils.run_pipe_test2(directory, filenames, top_entity, generics, test_generators, clk_name='clk')

if __name__ == '__main__':
    config.setup_logging(logging.DEBUG)
    test_axi_adder_with_pipe()
