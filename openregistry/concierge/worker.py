# -*- coding: utf-8 -*-
import argparse
import logging
import os
import time
import yaml

from couchdb.http import RETRYABLE_ERRORS

from openprocurement_client.registry_client import RegistryClient
from openprocurement_client.exceptions import InvalidResponse, Forbidden, RequestFailed

from .utils import prepare_couchdb, continuous_changes_feed

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(logging.Formatter('[%(asctime)s %(levelname)-5.5s] %(message)s'))
logger.addHandler(ch)


class BotWorker(object):
    def __init__(self, config, client):
        self.config = config
        self.sleep = self.config['time_to_sleep']
        self.lots_client = client(
            resource="lots",
            key=self.config['lots']['api']['token'],
            host_url=self.config['lots']['api']['url'],
            api_version=self.config['lots']['api']['version']
        )
        self.assets_client = client(
            resource="assets",
            key=self.config['assets']['api']['token'],
            host_url=self.config['assets']['api']['url'],
            api_version=self.config['assets']['api']['version']
        )
        if (self.config['db'].get('login', '') and self.config['db'].get('password', '')):
            db_url = "http://{login}:{password}@{host}:{port}".format(**self.config['db'])
        else:
            db_url = "http://{host}:{port}".format(**self.config['db'])

        self.db = prepare_couchdb(db_url, self.config['db']['name'], logger)

    def run(self):
        logger.info("Starting worker")
        for lot in self.get_lot():
            self.process_lots(lot)

    def get_lot(self):
        logger.info("Getting lots")
        try:
            return continuous_changes_feed(self.db, timeout=self.sleep,
                                           filter_doc=self.config['db']['filter'])
        except Exception, e:
            logger.error("Error while getting lots: {}".format(e))

    def process_lots(self, lot):
        logger.info("Processing lot {}".format(lot['id']))
        if lot['status'] == 'verification':
            try:
                assets_available = self.check_assets(lot)
            except RequestFailed:
                logger.info("Due to fail in getting assets, lot {} is skipped".format(lot['id']))
            if assets_available:
                try:
                    self.patch_assets(lot, 'verification', lot['id'])
                except Exception, e:
                    self.patch_assets(lot, 'pending', lot['id']) #  XXX TODO repatch to  pending status
                    logger.error("Error while pathching assets: {}".format(e))
                else:
                    self.patch_assets(lot, 'active', lot['id'])
                    self.patch_lot(lot, "active.salable")
            else:
                self.patch_lot(lot, "pending")
        elif lot['status'] == 'dissolved':
            self.patch_assets(lot, 'pending')

    def check_assets(self, lot):
        for asset_id in lot['assets']:
            try:
                asset = self.assets_client.get_asset(asset_id).data
                logger.info('Successfully got asset {}'.format(asset_id))
            except RequestFailed as e:
                logger.error('Falied to get asset: {}'.format(e.message))
                raise RequestFailed('Failed to get assets')
            if asset.status != 'pending':
                return False
        return True

    def patch_assets(self, lot, status, related_lot=None):
        for asset_id in lot['assets']:
            asset = {"data": {"id": asset_id, "status": status, "relatedLot": related_lot}}
            try:
                self.assets_client.patch_asset(asset)
            except (InvalidResponse, Forbidden, RequestFailed) as e:
                logger.error("Failed to patch asset {} to {} ({})".format(asset_id, status, e))
                return False
            else:
                logger.info("Successfully patched asset {} to {}".format(asset_id, status))
        return True

    def patch_lot(self, lot, status):
        lot['status'] = status
        try:
            self.lots_client.patch_lot({"data": lot})
        except (InvalidResponse, Forbidden, RequestFailed) as e:
            logger.error("Failed to patch lot {} to {}".format(lot['id'], status))
            return False
        else:
            logger.info("Successfully patched lot {} to {}".format(lot['id'], status))
            return True


def main():
    parser = argparse.ArgumentParser(description='---- Labot Worker ----')
    parser.add_argument('config', type=str, help='Path to configuration file')
    params = parser.parse_args()
    if os.path.isfile(params.config):
        with open(params.config) as config_object:
            config = yaml.load(config_object.read())
        BotWorker(config, RegistryClient).run()

if __name__ == "__main__":
    main()
