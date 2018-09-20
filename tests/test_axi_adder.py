import os

from slvcodec import config as slvcodec_config, test_utils
from axilent.examples import axi_adder
from axilent import coresdir

testoutput_dir = os.path.join(os.path.dirname(__file__), '..', 'test_outputs')

def test_axi_adder():
    tests = axi_adder.get_tests()
    slvcodec_config.setup_fusesoc(cores_roots=[coresdir])
    vu = slvcodec_config.setup_vunit(argv=['--dont-catch-exceptions'])
    for coretest in tests:
        test_utils.register_coretest_with_vunit(vu, coretest, testoutput_dir)
    all_ok = vu._main(post_run=None)
    assert all_ok

if __name__ == '__main__':
    test_axi_adder()
