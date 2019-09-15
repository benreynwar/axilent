import collections

from axilent import comms

# Response code for AXI.
OKAY = 0
EXOKAY = 1
SLVERR = 2
DECERR = 3


def make_empty_axi4lite_m2s_dict():
    '''
    Creates and empty master-to-slave AXI dictionary.
    '''
    return {
        'araddr': 0,
        'arprot': 0,
        'arvalid': 0,
        'awaddr': 0,
        'awprot': 0,
        'awvalid': 0,
        'bready': 1,
        'rready': 1,
        'wdata': 0,
        'wstrb': 15,
        'wvalid': 0,
    }


def make_axi4lite_m2s_dict(
        write_address=None, write_data=None, read_address=None,
        bready=0, rready=0):
    m2s = make_empty_axi4lite_m2s_dict()
    if write_address is not None:
        m2s['awaddr'] = write_address
        m2s['awvalid'] = 1
    if write_data is not None:
        m2s['wdata'] = write_data
        m2s['wvalid'] = 1
    if read_address is not None:
        m2s['araddr'] = read_address
        m2s['arvalid'] = 1
    m2s['bready'] = bready
    m2s['rready'] = rready
    return m2s


def make_empty_axi4lite_s2m_dict():
    '''
    Creates and empty slave-to-master AXI dictionary.
    '''
    return {
        'arready': 1,
        'awready': 1,
        'bresp': 0,
        'bvalid': 0,
        'rdata': 0,
        'rresp': 0,
        'rvalid': 0,
        'wready': 1,
    }


def make_axi4lite_s2m_dict(
        read_data=None, arready=0, awready=0, write_response=None, wready=0):
    s2m = make_empty_axi4lite_s2m_dict()
    s2m['arready'] = arready
    s2m['awready'] = awready
    if write_response is not None:
        s2m['bresp'] = write_response
        s2m['bvalid'] = 1
    if read_data is not None:
        s2m['rdata'] = read_data
        s2m['rvalid'] = 1
    s2m['wready'] = wready
    return s2m


def axi_commands_to_axi_dicts(axi_commands):
    ds = []
    for ac in axi_commands:
        if type(ac) in (comms.FakeWaitCommand, ):
            for i in range(ac.clock_cycles):
                ds.append(make_axi4lite_m2s_dict(bready=1, rready=1))
        else:
            for index in range(ac.length):
                d = make_axi4lite_m2s_dict(bready=1, rready=1)
                if ac.constant_address:
                    address = ac.start_address
                else:
                    address = ac.start_address + index
                if ac.readorwrite == comms.READ_TYPE:
                    d['araddr'] = address
                    d['arvalid'] = 1
                else:
                    d['awaddr'] = address
                    d['awvalid'] = 1
                    d['wvalid'] = 1
                    d['wdata'] = ac.data[index]
                    if d['wdata'] < 0:
                        raise Exception(
                            'Command {} is trying to set negative axi data'.format(ac))
                ds.append(d)
    return ds


def axi_dicts_to_axi_responses(axi_dicts):
    assert all([d['bvalid'] is not None for d in axi_dicts])
    assert all([d['rvalid'] is not None for d in axi_dicts])
    # Make sure that no inputs got dropped.
    assert all([d['arready'] for d in axi_dicts if d['arvalid']])
    assert all([d['awready'] for d in axi_dicts if d['awvalid']])
    assert all([d['wready'] for d in axi_dicts if d['wvalid']])
    write_ds = [d for d in axi_dicts if d['bvalid'] and d['bready']]
    read_ds = [d for d in axi_dicts if d['rvalid'] and d['rready']]
    write_responses = collections.deque([
        comms.AxiResponse(length=1, data=[None], resp=d['bresp']) for d in write_ds])
    read_responses = collections.deque([
        comms.AxiResponse(length=1, data=[d['rdata']], resp=d['rresp'])
        for d in read_ds])
    return read_responses, write_responses
