import os
import logging
import shutil

from slvcodec import config as slvcodec_config, test_utils, event
from axilent.examples import axi_adder, axi_adder_pipe
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


def test_axi_adder_pipe():
    directory = os.path.join(testoutput_dir, 'axi_adder_pipe')
    if os.path.exists(directory):
        shutil.rmtree(directory)
    os.makedirs(directory)

    top_entity = 'axi_adder'
    filenames = [
        '/home/ben/Code/axilent/axilent/vhdl/axi_utils.vhd',
        '/home/ben/Code/axilent/axilent/vhdl/axi_adder.vhd',
        ]
    generics = {}

    simulator = event.Simulator(directory, filenames, top_entity, generics)
    loop = event.EventLoop(simulator)
    handler = handlers.NamedPipeHandler(
        dut=simulator.dut,
        loop=loop,
        in_name='m2s',
        out_name='s2m',
        )

    loop.create_task(handler.communicate())
    loop.create_task(axi_adder.axi_adder_test(handler))
    loop.run_forever()


if __name__ == '__main__':
    config.setup_logging(logging.INFO)
    test_axi_adder_pipe()
