import os
from setuptools import setup

this_directory = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(this_directory, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()


setup(
    name='axilent',
    packages=['axilent', 'axilent.examples'],
    package_data={'': ['vhdl/*.core', 'vhdl/*.vhd']},
    use_scm_version={
        'relative_to': __file__,
        'write_to': 'axilent/version.py',
    },
    setup_requires=['setuptools_scm'],
    author='Ben Reynwar',
    author_email='ben@reynwar.net',
    description=('Tools for describing a sequence of Axi4Lite commands.'),
    long_description=long_description,
    long_description_content_type='text/x-rst',
    license='MIT',
    keywords=['VHDL', 'hdl', 'rtl', 'FPGA', 'ASIC', 'Xilinx', 'Altera'],
    url='https://github.com/benreynwar/axilent',
    install_requires=[
        'jinja2>=2.8',
        'pytest',
        'slvcodec>=0.3.5',
    ],
)
