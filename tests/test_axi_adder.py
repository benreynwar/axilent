import os
import logging
import shutil

import pytest
from slvcodec import config as slvcodec_config, test_utils, event

from axilent.examples import axi_adder
from axilent import coresdir, handlers, config


testoutput_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'test_outputs'))

logger = logging.getLogger(__name__)

fusesoc_config_filename = config.get_fusesoc_config_filename()


def test_axi_adder():
    tests = axi_adder.get_tests()
    vu = slvcodec_config.setup_vunit(argv=['--dont-catch-exceptions'])
    for coretest in tests:
        test_utils.register_coretest_with_vunit(
            vu, coretest, testoutput_dir, fusesoc_config_filename=fusesoc_config_filename)
    all_ok = vu._main(post_run=None)
    assert all_ok


@pytest.mark.skip
def test_axi_adder_pipe():
    directory = os.path.join(testoutput_dir, 'axi_adder_pipe')
    if os.path.exists(directory):
        shutil.rmtree(directory)
    os.makedirs(directory)

    top_entity = 'axi_adder'
    filenames = [os.path.join(config.basedir, 'vhdl', fn) for fn in (
        'axi_utils.vhd',
        'axi_adder_pkg.vhd',
        'axi_adder_assertions.vhd',
        'axi_adder.vhd',
        )]
    generics = {}

    simulator = event.Simulator(directory, filenames, top_entity, generics)
    loop = event.EventLoop(simulator)
    handler = handlers.NamedPipeHandler(
        loop=loop,
        m2s=simulator.dut.m2s,
        s2m=simulator.dut.s2m,
        )
    loop.create_task(handler.communicate())
    loop.create_task(axi_adder.axi_adder_test(simulator.dut, handler))
    loop.run_forever()


@pytest.mark.skip
def test_axi_adder_assertions():
    directory = os.path.join(testoutput_dir, 'axi_adder_assertions')
    if os.path.exists(directory):
        shutil.rmtree(directory)
    os.makedirs(directory)

    top_entity = 'axi_adder_assertions'
    filenames = [os.path.join(config.basedir, 'vhdl', fn) for fn in (
        'axi_utils.vhd',
        'axi_adder_pkg.vhd',
        'axi_adder_assertions.vhd',
        )]
    generics = {'max_delay': 4,}

    simulator = event.Simulator(directory, filenames, top_entity, generics)
    loop = event.EventLoop(simulator)
    loop.create_task(axi_adder.axi_adder_assertions_test(simulator.dut))
    loop.run_forever()
