library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

use work.axi_utils.all;

entity axi_adder is
  --- Address 0: read/write to intA
  --- Address 1: read/write to intB
  --- Address 2: read only to intC
  --- intC = intA + intB
  port (
    clk: in std_logic;
    reset: in std_logic;
    m2s: in axi4lite_m2s;
    s2m: out axi4lite_s2m
    );
end axi_adder;

architecture arch of axi_adder is
  -- Merged aw and w streams
  signal cw_valid: std_logic;
  signal cw_ready: std_logic;
  signal cw_address: unsigned(31 downto 0);
  signal cw_data: std_logic_vector(31 downto 0);

  signal b_valid: std_logic;
  signal b_ready: std_logic;
  signal b_resp: std_logic_vector(1 downto 0);

  signal ar_valid: std_logic;
  signal ar_ready: std_logic;
  signal ar_address: unsigned(31 downto 0);

  signal r_valid: std_logic;
  signal r_ready: std_logic;
  signal r_resp: std_logic_vector(1 downto 0);
  signal r_data: std_logic_vector(31 downto 0);
  
  signal m_A: unsigned(15 downto 0);
  signal m_B: unsigned(15 downto 0);
  signal C: unsigned(16 downto 0);
begin

  cw_valid <= m2s.awvalid and m2s.wvalid;
  s2m.awready <= cw_ready and m2s.wvalid;
  s2m.wready <= cw_ready and m2s.awvalid;
  cw_address <= unsigned(m2s.awaddr);
  cw_data <= m2s.wdata;

  cw_ready <= b_ready or not b_valid;
  b_ready <= m2s.bready;
  s2m.bvalid <= b_valid;
  s2m.bresp <= b_resp;

  ar_valid <= m2s.arvalid;
  s2m.arready <= ar_ready;
  ar_address <= unsigned(m2s.araddr);

  ar_ready <= r_ready or not r_valid;
  r_ready <= m2s.rready;
  s2m.rvalid <= r_valid;
  s2m.rresp <= r_resp;
  s2m.rdata <= r_data;

  C <= resize(m_A, 17) + resize(m_B, 17);

    
  process(clk)
  begin
    if rising_edge(clk) then
      if reset = '1' then
        m_A <= (others => '0');
        m_B <= (others => '0');
        b_valid <= '0';
        r_valid <= '0';
      else
        -- Handle writing of registers.
        if (cw_valid = '1') and (cw_ready = '1') then
          b_valid <= '1';
          if cw_address = 0 then
            m_A <= unsigned(m2s.wdata(15 downto 0));
            b_resp <= axi_resp_OKAY;
          elsif cw_address = 1 then
            m_B <= unsigned(m2s.wdata(15 downto 0));
            b_resp <= axi_resp_OKAY;
          else
            b_resp <= axi_resp_DECERR;
          end if;
        elsif b_ready = '1' then
          b_valid <= '0';
        end if;
        -- Handle reading of registers.
        if (ar_valid = '1') and (ar_ready = '1') then
          r_valid <= '1';
          if ar_address = 0 then
            
            r_data <= std_logic_vector(resize(m_A, 32));
          elsif ar_address = 1 then
            r_resp <= axi_resp_OKAY;
            r_data <= std_logic_vector(resize(m_B, 32));
          elsif ar_address = 2 then
            r_resp <= axi_resp_OKAY;
            r_data <= std_logic_vector(resize(C, 32));
          else
            r_resp <= axi_resp_DECERR;
          end if;
        elsif r_ready = '1' then
          r_valid <= '0';
        end if;
      end if;
    end if;
  end process;
  
end arch;
