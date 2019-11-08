import os
import json
import logging
import random

from slvcodec import cocotb_wrapper as cocotb
from slvcodec.cocotb_wrapper import triggers, result
from slvcodec import cocotb_dut
from slvcodec import test_utils as slvcodec_test_utils
from slvcodec import config as slvcodec_config

from axilent.examples import axi_adder
from axilent import cocotb_handler, config, test_utils


logger = logging.getLogger(__name__)

testoutput_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'test_outputs'))


fusesoc_config_filename = config.get_fusesoc_config_filename()


def test_axi_adder():
    tests = get_tests()
    vu = slvcodec_config.setup_vunit(argv=['--dont-catch-exceptions'])
    for coretest in tests:
        slvcodec_test_utils.register_coretest_with_vunit(
            vu, coretest, testoutput_dir, fusesoc_config_filename=fusesoc_config_filename)
    all_ok = vu._main(post_run=None)
    assert all_ok


@cocotb.coroutine
async def axi_adder_test(handler):
    comm = axi_adder.AxiAdderComm(address_offset=0, handler=handler)
    n_data = 100
    max_int = pow(2, 16)-1
    for i in range(n_data):
        inta = random.randint(0, max_int)
        intb = random.randint(0, max_int)
        intc = await comm.add_numbers_async(inta, intb)
        assert intc == inta + intb
    raise result.TestSuccess()


def make_handler(dut):
    axi_handler = cocotb_handler.CocotbHandler(dut.clk, m2s=dut.m2s, s2m=dut.s2m)
    axi_handler.start()
    return axi_handler


@cocotb.test()
async def axi_adder_test_top(dut):
    params_filename = os.environ['test_params_filename']
    with open(params_filename) as f:
        params = json.load(f)
    mapping = params['mapping']
    cocotb_dut.apply_mapping(dut, mapping, separator='_')
    cocotb.fork(slvcodec_test_utils.clock(dut.clk))
    dut.reset <= 0
    await triggers.RisingEdge(dut.clk)
    dut.reset <= 1
    await triggers.RisingEdge(dut.clk)
    dut.reset <= 0
    await triggers.RisingEdge(dut.clk)
    axi_handler = make_handler(dut)
    await axi_adder_test(axi_handler)


def make_coro(generics, top_params):
    async def coro(dut, resolved):
        dut.reset <= 0
        await triggers.RisingEdge(dut.clk)
        dut.reset <= 1
        await triggers.RisingEdge(dut.clk)
        dut.reset <= 0
        axi_handler = make_handler(dut)
        await axi_adder_test(axi_handler)
    return coro

def make_ftb_test(generics, top_params, resolved):
    axi_test = axi_adder.AxiAdderTest()
    test = test_utils.DictAxiTest(axi_test)
    return test

def get_tests():
    def make_test_params(resolved):
        return {}
    test = {
        'core_name': 'axi_adder',
        'entity_name': 'axi_adder',
        'generics': {'formal': False},
        'top_params': {},
        'test_module_name': 'test_axi_adder',
        'test_params': make_test_params,
        'coro': make_coro,
        'generator': make_ftb_test,
        }
    return [test]


def test_cocotb():
    test_output_directory = os.path.abspath('axi_adder_cocotb')
    tests = get_tests()
    for test in tests:
        slvcodec_test_utils.run_coretest_with_cocotb(
            test, test_output_directory,
            fusesoc_config_filename=config.get_fusesoc_config_filename(),
            generate_iteratively=False)


def test_pipes():
    test_output_directory = os.path.abspath('axi_adder_pipes')
    tests = get_tests()
    for test in tests:
        slvcodec_test_utils.run_coretest_with_pipes(
            test, test_output_directory,
            fusesoc_config_filename=config.get_fusesoc_config_filename(),
            generate_iteratively=False)


if __name__ == '__main__':
    test_cocotb()
