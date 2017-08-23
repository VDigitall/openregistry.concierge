# -*- coding: utf-8 -*-
from couchdb import Server, Session
from socket import error
from time import sleep

from .design import sync_design

CONTINUOUS_CHANGES_FEED_FLAG = True


class ConfigError(Exception):
    pass


def prepare_couchdb(couch_url, db_name, logger):
    server = Server(couch_url, session=Session(retry_delays=range(10)))
    try:
        if db_name not in server:
            db = server.create(db_name)
        else:
            db = server[db_name]
    except error as e:
        logger.error('Database error: {}'.format(e.message))
        raise ConfigError(e.strerror)
    sync_design(db)
    return db


def continuous_changes_feed(db, logger, timeout=10, limit=100,
                            filter_doc='lots/status'):
    last_seq_id = 0
    while CONTINUOUS_CHANGES_FEED_FLAG:
        logger.info('Getting Lots')
        data = db.changes(include_docs=True, since=last_seq_id, limit=limit,
                          filter=filter_doc)
        last_seq_id = data['last_seq']
        if len(data['results']) != 0:
            for row in data['results']:
                item = {
                    'id': row['doc']['_id'],
                    'status': row['doc']['status'],
                    'assets': row['doc']['assets'],
                    'lotID': row['doc']['lotID']
                }
                yield item
        else:
            sleep(timeout)
