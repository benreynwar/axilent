library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

use work.axi_utils.all;
use work.axi_adder_pkg.all;

entity axi_adder_unwrapped is
  --- Address 0: read/write to intA
  --- Address 1: read/write to intB
  --- Address 2: read only to intC
  --- intC = intA + intB
  generic (
    FORMAL: boolean := true
    );
  port (
    assertions: out t_axi_adder_assertions;
    clk: in std_logic;
    reset: in std_logic;
    araddr: in std_logic_vector(31 downto 0); 
    arprot: in std_logic_vector(2 downto 0);
    arvalid: in std_logic;
    awaddr: in std_logic_vector(31 downto 0); 
    awprot: in std_logic_vector(2 downto 0);
    awvalid: in std_logic; 
    bready: in std_logic;
    rready: in std_logic;
    wdata: in std_logic_vector(31 downto 0); 
    wstrb: in std_logic_vector(3 downto 0);
    wvalid: in std_logic;
    arready: out std_logic;
    awready: out std_logic; 
    bresp: out std_logic_vector(1 downto 0);
    bvalid: out std_logic;
    rdata: out std_logic_vector(31 downto 0);
    rresp: out std_logic_vector(1 downto 0);
    rvalid: out std_logic;
    wready: out std_logic
    );
end axi_adder_unwrapped;

architecture arch of axi_adder_unwrapped is
  
  signal m2s: axi4lite_m2s;
  signal s2m: axi4lite_s2m;
begin

  m2s.araddr <= araddr;
  m2s.arprot <= arprot;
  m2s.arvalid <= arvalid;
  m2s.awaddr <= awaddr;
  m2s.awprot <= awprot;
  m2s.awvalid <= awvalid;
  m2s.bready <= bready;
  m2s.rready <= rready;
  m2s.wdata <= wdata;
  m2s.wstrb <= wstrb;
  m2s.wvalid <= wvalid;

  arready <= s2m.arready;
  awready <= s2m.awready;
  bresp <= s2m.bresp;
  bvalid <= s2m.bvalid;
  rdata <= s2m.rdata;
  rresp <= s2m.rresp;
  rvalid <= s2m.rvalid;
  wready <= s2m.wready;

  wrapped: entity work.axi_adder
    generic map (
      FORMAL => FORMAL
      )
    port map (
      clk => clk,
      reset => reset,
      assertions => assertions,
      m2s => m2s,
      s2m => s2m
      );
  
end arch;
