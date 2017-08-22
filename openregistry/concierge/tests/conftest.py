# -*- coding: utf-8 -*-
import logging
import pytest

from StringIO import StringIO

from openregistry.concierge.worker import BotWorker, logger as LOGGER

TEST_CONFIG = {
  "API_URL": "http://192.168.50.9:80/",
  "API_VERSION": "0.1",
  "LOTS_DB": {
    "host": "192.168.50.9",
    "db": "openregistry",
    "port": "5990",
    "login": "admin",
    "password": "admin",
    "view": "lots/by_dateModified"
  },
  "ASSETS_API_TOKEN": "bot",
  "LOTS_API_TOKEN": "bot1",
  "TIME_TO_SLEEP": 10
}


@pytest.fixture(scope='function')
def mock_client(mocker):
    return mocker.patch('openprocurement_client.registry_client.RegistryClient', spec=True)


@pytest.fixture(scope='function')
def bot(mock_client, moker):
    mocker.patch('openregistry.concierge.worker.LotsClient',
                 spec=True)
    mocker.patch('openregistry.concierge.worker.AssetsClient',
                 spec=True)
    return BotWorker(TEST_CONFIG)


class LogInterceptor(object):
    def __init__(self, logger):
        self.log_capture_string = StringIO()
        self.test_handler = logging.StreamHandler(self.log_capture_string)
        self.test_handler.setLevel(logging.INFO)
        logger.addHandler(self.test_handler)


@pytest.fixture(scope='function')
def logger():
    return LogInterceptor(LOGGER)


class AlmostAlwaysTrue(object):
    def __init__(self, total_iterations=1):
        self.total_iterations = total_iterations
        self.current_iteration = 0

    def __nonzero__(self):
        if self.current_iteration < self.total_iterations:
            self.current_iteration += 1
            return bool(1)
        return bool(0)


@pytest.fixture(scope='function')
def almost_always_true():
    return AlmostAlwaysTrue(2)
