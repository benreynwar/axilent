from setuptools import setup

setup(
    name='axilent',
    packages=['axilent', 'axilent.examples'],
    package_data={'': ['cores/*.core', 'vhdl/*.vhd']},
    use_scm_version={
        'relative_to': __file__,
        'write_to': 'axilent/version.py',
    },
    author='Ben Reynwar',
    author_email='ben@reynwar.net',
    description=(''),
    license='MIT',
    keywords=['VHDL', 'hdl', 'rtl', 'FPGA', 'ASIC', 'Xilinx', 'Altera'],
    url='https://github.com/benreynwar/axilent',
    install_requires=[
    ],
    dependency_links=[
    ],
)
