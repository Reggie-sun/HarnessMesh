import pytest


def pytest_addoption(parser):
    parser.addoption('--containment-conformance', action='store_true', default=False,
                     help='Run synthetic adversarial tests in pinned local Docker image')
    parser.addoption('--native-conformance', action='store_true', default=False,
                     help='Run installed trusted CLI against loopback fake upstream; never live')


def pytest_collection_modifyitems(config, items):
    if not config.getoption('--containment-conformance'):
        for item in items:
            if 'containment' in item.keywords:
                item.add_marker(pytest.mark.skip(reason='requires explicit --containment-conformance'))
    if not config.getoption('--native-conformance'):
        for item in items:
            if 'native' in item.keywords:
                item.add_marker(pytest.mark.skip(reason='requires explicit --native-conformance'))
