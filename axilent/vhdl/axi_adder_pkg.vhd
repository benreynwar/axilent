library ieee;
use ieee.std_logic_1164.all;

package axi_adder_pkg is

  type t_axi_adder_local_output_assertions is
  record
    ar_mismatch: std_logic;
    aw_mismatch: std_logic;
    w_mismatch: std_logic;
  end record;

  type t_axi_adder_assertions is
  record
    output: t_axi_adder_local_output_assertions;
  end record;

  constant NULL_AXI_ADDER_ASSERTIONS: t_axi_adder_assertions := 
    (others => (others => '0'));

end package;
