library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

use work.axi_utils.all;
use work.axi_adder_pkg.all;

entity axi_adder_assertions is
  --generic (
  --  MAX_DELAY: positive
  --  );
  port (
    assertions: out t_axi_adder_assertions;
    clk: in std_logic;
    reset: in std_logic;
    m2s: in axi4lite_m2s;
    s2m: in axi4lite_s2m
    );
end entity;
 
architecture arch of axi_adder_assertions is
  signal ar_fire: std_logic;
  signal aw_fire: std_logic;
  signal w_fire: std_logic;
  signal b_fire: std_logic;
  signal r_fire: std_logic;

  signal wait_count: signed(31 downto 0);
  signal ar_unresolved: unsigned(31 downto 0);
  signal aw_unresolved: unsigned(31 downto 0);
  signal w_unresolved: unsigned(31 downto 0);

  signal has_reset: std_logic := '0';

  signal assertions_c: t_axi_adder_assertions;

  signal hit_max_delay: std_logic;
begin
  assertions <= assertions_c;

  ar_fire <= m2s.arvalid and s2m.arready;
  aw_fire <= m2s.awvalid and s2m.awready;
  w_fire <= m2s.wvalid and s2m.wready;
  b_fire <= s2m.bvalid and m2s.bready;
  r_fire <= s2m.rvalid and m2s.rready;

    --assert (assertions.output.ar_mismatch and has_reset) = '0';
    --assert (assertions.output.aw_mismatch and has_reset)= '0';
    --assert (assertions.output.w_mismatch and has_reset)= '0';

  process(clk)
  begin
    if rising_edge(clk) then
      assertions_c.output.ar_mismatch <= '0';
      assertions_c.output.aw_mismatch <= '0';
      assertions_c.output.w_mismatch <= '0';
      if (m2s.awvalid = '0') and (m2s.wvalid = '0') and (m2s.arvalid = '0') and (m2s.rready = '1') and (m2s.bready = '1') then
        wait_count <= wait_count + 1;
      else
        wait_count <= (others => '0');
      end if;
      hit_max_delay <= '0';
      --if wait_count = MAX_DELAY then
      if wait_count = 4 then
        hit_max_delay <= '1';
        if w_unresolved /= 0 then
          assertions_c.output.w_mismatch <= '1';
        end if;
        if ar_unresolved /= 0 then
          assertions_c.output.ar_mismatch <= '1';
        end if;
        if aw_unresolved /= 0 then
          assertions_c.output.aw_mismatch <= '1';
        end if;
      end if;

      if ar_fire = '1' and r_fire = '0' then
        ar_unresolved <= ar_unresolved + 1;
      elsif ar_fire = '0' and r_fire = '1' then
        ar_unresolved <= ar_unresolved - 1;
      end if;
      if aw_fire = '1' and b_fire = '0' then
        aw_unresolved <= aw_unresolved + 1;
      elsif aw_fire = '0' and b_fire = '1' then
        aw_unresolved <= aw_unresolved - 1;
      end if;
      if w_fire = '1' and b_fire = '0' then
        w_unresolved <= w_unresolved + 1;
      elsif w_fire = '0' and b_fire = '1' then
        w_unresolved <= w_unresolved - 1;
      end if;

      if reset = '1' then
        ar_unresolved <= (others => '0');
        aw_unresolved <= (others => '0');
        w_unresolved <= (others => '0');
        has_reset <= '1';
        assertions_c.output.ar_mismatch <= '0';
        assertions_c.output.aw_mismatch <= '0';
        assertions_c.output.w_mismatch <= '0';
      end if;
      
    end if;
  end process;
  
end arch;
