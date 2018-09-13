# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2018, Galen Curwen-McAdams

import argparse
import redis

def main():
    # should provide cli acceses to structuring / sequencing
    # and do everything / more than fold-ui
    # as done in visualizations.structure_preview
    #
    # for now just gather all glworbs and create/overwrite
    # sequence key
    # useful for testing without running fold-ui

    parser = argparse.ArgumentParser()
    parser.add_argument("--db-host",  default="127.0.0.1", help="db host ip")
    parser.add_argument("--db-port", type=int, default=6379, help="db port")
    parser.add_argument("--db-sources-template",  default="machinic:structured:{host}:{port}", help="a list key")
    parser.add_argument("--db-sources-prefix",  default="glworb:*", help="db prefix to pattern match")
    parser.add_argument("--verbose", action="store_true", help="")
    args = parser.parse_args()

    db_settings = {"host" :  args.db_host, "port" : args.db_port}
    redis_conn = redis.StrictRedis(**db_settings, decode_responses=True)

    structured_sources_key = args.db_sources_template.format(host=args.db_host, port=args.db_port)
    redis_conn.delete(structured_sources_key)
    sources =  sorted(list(redis_conn.scan_iter(match=args.db_sources_prefix)))

    for source in sources:
        redis_conn.lpush(structured_sources_key, source)
