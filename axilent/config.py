import os
import logging
import jinja2

basedir = os.path.abspath(os.path.dirname(__file__))


def get_fusesoc_config_filename():
    template_filename = os.path.join(basedir, 'fusesoc.conf.j2')
    output_filename = os.path.join(basedir, 'fusesoc.conf')
    if not os.path.exists(output_filename):
        with open(template_filename, 'r') as f:
            template = jinja2.Template(f.read())
        content = template.render(basedir=basedir)
        with open(output_filename, 'w') as f:
            f.write(content)
    return output_filename


def setup_logging(level):
    '''
    Utility function for setting up logging.
    Configured for when slvcodec is being tested rather than used.
    '''
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    ch.setFormatter(formatter)
    # Which packages do we want to log from.
    packages = ('__main__', 'slvcodec', 'axilent')
    for package in packages:
        logger = logging.getLogger(package)
        logger.addHandler(ch)
        logger.setLevel(level)
    # Warning only packages
    packages = []
    for package in packages:
        logger = logging.getLogger(package)
        logger.addHandler(ch)
        logger.setLevel(logging.WARNING)
    logger.info('Setup logging at level {}.'.format(level))
