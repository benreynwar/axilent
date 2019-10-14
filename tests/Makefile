SIM = ghdl
VHDL_DIR = $(abspath ../axilent/vhdl)
VHDL_SOURCES = \
    $(VHDL_DIR)/axi_utils.vhd \
    $(VHDL_DIR)/axi_adder_pkg.vhd \
    $(VHDL_DIR)/axi_adder_assertions.vhd \
    $(VHDL_DIR)/axi_adder.vhd \
    $(VHDL_DIR)/axi_adder_unwrapped.vhd \

# TOPLEVEL is the name of the toplevel module in your Verilog or VHDL file:
TOPLEVEL=axi_adder_unwrapped

EXTRA_ARGS="-gFORMAL=0"

# MODULE is the name of the Python test file:
MODULE=test_axi_adder

include $(shell cocotb-config --makefiles)/Makefile.inc
include $(shell cocotb-config --makefiles)/Makefile.sim
