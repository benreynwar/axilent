import pytest
cocotb = pytest.importorskip('cocotb')

from axilent.examples import axi_adder
from axilent import cocotb_handler


@pytest.mark.skip(reason='Run using cocotb Makefile.')
@cocotb.test()
async def test_axi_adder_cocotb(dut):
    axi_signals = {
        'wvalid': dut.wvalid,
        'wready': dut.wready,
        'wdata': dut.wdata,
        'awvalid': dut.awvalid,
        'awready': dut.awready,
        'awaddr': dut.awaddr,
        'bvalid': dut.bvalid,
        'bready': dut.bready,
        'bresp': dut.bresp,
        'arvalid': dut.arvalid,
        'arready': dut.arready,
        'araddr': dut.araddr,
        'rvalid': dut.rvalid,
        'rready': dut.rready,
        'rresp': dut.rresp,
        'rdata': dut.rdata,
        }
    handler = cocotb_handler.CocotbHandler(dut.clk, 10, dut.reset, axi_signals, dut.log)
    await handler.start()
    await cocotb.coroutine(axi_adder.axi_adder_test)(dut, handler)
