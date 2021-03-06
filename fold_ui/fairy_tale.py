# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2018, Galen Curwen-McAdams

import argparse
import redis
import time
import uuid
import io
import random
import sys
import itertools
from PIL import Image as PILImage, ImageDraw, ImageColor, ImageFont
from ma_cli import data_models

# generate structured(and destructured) test material for fold-lattice-ui
#
# fold-ui-fairytale --part-field-values part part1 part2
#                   --part-part-amounts 10 10
#                   --part-increment-field page_number
#                   --part-binary-field binary_key
#                   --db-prefix glworb:
#                   --db-expire-in 100
#                   --verbose

r_ip, r_port = data_models.service_connection()
binary_r = redis.StrictRedis(host=r_ip, port=r_port)
redis_conn = redis.StrictRedis(host=r_ip, port=r_port, decode_responses=True)


def generate_things(**kwargs):
    global binary_r
    global redis_conn
    if kwargs["db_host"] and kwargs["db_port"]:
        binary_r = redis.StrictRedis(host=kwargs["db_host"], port=kwargs["db_port"])
        redis_conn = redis.StrictRedis(
            host=kwargs["db_host"], port=kwargs["db_port"], decode_responses=True
        )

    if kwargs["db_del_pattern"]:
        for db_del_pattern in kwargs["db_del_pattern"]:
            for matched_key in redis_conn.scan_iter(match=db_del_pattern):
                if kwargs["db_del_field"]:
                    if kwargs["db_del_field"] in redis_conn.hgetall(matched_key).keys():
                        redis_conn.delete(matched_key)
                        if kwargs["verbose"]:
                            print("deleted: {}".format(matched_key))
                else:
                    redis_conn.delete(matched_key)
                    if kwargs["verbose"]:
                        print("deleted: {}".format(matched_key))

    try:
        field_name, *field_values = kwargs["part_field_values"]
    except TypeError:
        sys.exit()

    things = []
    kwargs["part_part_amounts"] = [int(s) for s in kwargs["part_part_amounts"]]
    if kwargs["part_part_amounts_start"] is None:
        kwargs["part_part_amounts_start"] = []
    kwargs["part_part_amounts_start"] = [
        int(s) for s in kwargs["part_part_amounts_start"]
    ]
    kwargs["part_part_amounts_start"] += [0] * (
        len(kwargs["part_part_amounts"]) - len(kwargs["part_part_amounts_start"])
    )

    to_disorder = kwargs["structure_disorder"]

    missed = 0
    duplicated = 0
    disordered = 0

    to_miss = []
    while len(to_miss) < kwargs["structure_missing"]:
        for part, amount in zip(field_values, kwargs["part_part_amounts"]):
            if len(to_miss) < kwargs["structure_missing"]:
                to_miss.append(
                    (
                        random.randint(0, len(field_values) - 1),
                        random.randint(0, amount),
                    )
                )

    to_duplicate = []
    while len(to_duplicate) < kwargs["structure_duplicate"]:
        for part, amount in zip(field_values, kwargs["part_part_amounts"]):
            if len(to_duplicate) < kwargs["structure_duplicate"]:
                to_duplicate.append(
                    (
                        random.randint(0, len(field_values) - 1),
                        random.randint(0, amount),
                    )
                )

    expire_interval = 0
    part_num = 0
    for part, amount, amount_start in zip(
        field_values, kwargs["part_part_amounts"], kwargs["part_part_amounts_start"]
    ):
        print(part, part_num)
        for sequence_number in range(amount):
            duplicates = 1
            if not (part_num, sequence_number) in to_miss:
                if (part_num, sequence_number) in to_duplicate:
                    duplicates = 2
                    to_duplicate.remove((part_num, sequence_number))
                    duplicated += 1
                    if kwargs["verbose"]:
                        print("duplicate:", (part_num, sequence_number))
                for _ in range(duplicates):
                    thing = {}
                    thing[field_name] = part
                    # add an incrementing field
                    if kwargs["part_increment_field"]:
                        thing[kwargs["part_increment_field"]] = (
                            sequence_number + amount_start
                        )
                    # add a binary field / key
                    if kwargs["part_binary_field"]:
                        db_binary_key = kwargs["part_binary_prefix"] + str(uuid.uuid4())
                        thing[kwargs["part_binary_field"]] = db_binary_key
                        binary_bytes = generate_image(
                            sequence_number,
                            kwargs["binary_width"],
                            kwargs["binary_height"],
                        )
                        binary_r.set(db_binary_key, binary_bytes)
                        if kwargs["db_expire_in"] > 0:
                            redis_conn.expire(
                                db_binary_key, kwargs["db_expire_in"] + expire_interval
                            )
                            expire_interval += kwargs["db_expire_interval"]

                        if kwargs["verbose"]:
                            print(db_binary_key)
                    things.append(thing)
            else:
                if kwargs["verbose"]:
                    print("missing:", (part_num, sequence_number))
                to_miss.remove((part_num, sequence_number))
                missed += 1
        part_num += 1

    while to_disorder > 0:
        pos1 = random.randint(0, len(things) - 1)
        pos2 = random.randint(0, len(things) - 1)
        things[pos1], things[pos2] = things[pos2], things[pos1]
        if kwargs["verbose"]:
            print("disordered:", (pos1, pos2))
        to_disorder -= 1
        disordered += 1

    expire_interval = 0

    for content in things:
        db_key = kwargs["db_prefix"] + str(uuid.uuid4())
        redis_conn.hmset(db_key, content)
        if kwargs["verbose"]:
            print(db_key)
            print(content)
        if kwargs["db_expire_in"] > 0:
            redis_conn.expire(db_key, kwargs["db_expire_in"] + expire_interval)
            expire_interval += kwargs["db_expire_interval"]

        time.sleep(kwargs["structure_stagger_delay"])

    if kwargs["verbose"]:
        print("hash keys: {}".format(len(things)))
        print(
            "missed: {}\nduplicated: {}\ndisordered:{}".format(
                missed, duplicated, disordered
            )
        )


def generate_image(text, width, height, background_color="lightgray"):

    img = PILImage.new("RGB", (width, height), background_color)
    draw = ImageDraw.Draw(img, "RGBA")

    try:
        font = ImageFont.truetype("DejaVuSerif-Bold.ttf", 20)
    except Exception as ex:
        print(ex)
        font = None

    x = int(width / 2)
    y = int(height / 2)
    draw.text((x, y), str(text), fill="black", font=font)
    file = io.BytesIO()
    extension = "JPEG"
    img.save(file, extension)
    img.close()
    file.seek(0)
    return file.getvalue()


def ingest_things(**kwargs):
    global binary_r
    global redis_conn
    if kwargs["db_host"] and kwargs["db_port"]:
        binary_r = redis.StrictRedis(host=kwargs["db_host"], port=kwargs["db_port"])
        redis_conn = redis.StrictRedis(
            host=kwargs["db_host"], port=kwargs["db_port"], decode_responses=True
        )

    if kwargs["db_del_pattern"]:
        for db_del_pattern in kwargs["db_del_pattern"]:
            for matched_key in redis_conn.scan_iter(match=db_del_pattern):
                if kwargs["db_del_field"]:
                    if kwargs["db_del_field"] in redis_conn.hgetall(matched_key).keys():
                        redis_conn.delete(matched_key)
                        if kwargs["verbose"]:
                            print("deleted: {}".format(matched_key))
                else:
                    redis_conn.delete(matched_key)
                    if kwargs["verbose"]:
                        print("deleted: {}".format(matched_key))

    to_mislabel_span_integer = {}
    if kwargs["ingest_mislabel_span_integer"]:
        for field_name, span_amount, span_range in kwargs[
            "ingest_mislabel_span_integer"
        ]:
            if field_name not in to_mislabel_span_integer:
                to_mislabel_span_integer[field_name] = []
            span_start = random.randint(0, int(span_range))
            # list is [start position, amount (to decrement), span_start_value]
            to_mislabel_span_integer[field_name] = [span_start, int(span_amount), 0]

    to_mislabel_span_badstr = {}
    if kwargs["ingest_mislabel_span_badstr"]:
        for field_name, span_amount, span_range in kwargs[
            "ingest_mislabel_span_badstr"
        ]:
            if field_name not in to_mislabel_span_badstr:
                to_mislabel_span_badstr[field_name] = []
            span_start = random.randint(0, int(span_range))
            # list is [start position, amount (to decrement), span_start_value]
            to_mislabel_span_badstr[field_name] = [span_start, int(span_amount), 0]

    cycling_fields = {}
    if kwargs["field_cycle"]:
        for cycle_field in kwargs["field_cycle"]:
            cycling_fields[cycle_field[0]] = itertools.cycle(cycle_field[1:])
    if kwargs["ingest_manifest"].endswith(".csv"):
        import csv

        write_to_db = []
        # check if the csv has a header
        # used for line_offset
        with open(kwargs["ingest_manifest"], "r") as csv_file:
            sniffer = csv.Sniffer()
            csv_has_header = sniffer.has_header(csv_file.read(2048))

        # calculate a line_offset for use with --ingest-manifest-lines
        # since the line number seen using less -N file.csv
        # includes the csv header(if one exists) and starts at 1
        # whereas the reader enumeration begins at 0 with csv header not included
        if csv_has_header:
            line_offset = 2
        else:
            line_offset = 1

        with open(kwargs["ingest_manifest"], "r") as csv_file:
            reader = csv.DictReader(csv_file)
            for row_num, row in enumerate(reader):
                db_hash = {}
                if (
                    not kwargs["ingest_manifest_lines"]
                    or row_num + line_offset in kwargs["ingest_manifest_lines"]
                ):
                    print(row_num)
                    for k, v in row.items():
                        key = k
                        for source, dest in kwargs["ingest_map"]:
                            if source == k:
                                key = dest
                        if k in kwargs["ingest_as_binary"]:
                            bytes_key = "{}{}".format(
                                kwargs["ingest_binary_prefix"], str(uuid.uuid4())
                            )
                            binary_r.set(bytes_key, ingest_file(v))
                            db_hash[key] = bytes_key
                        else:
                            db_hash[key] = v

                        if key in to_mislabel_span_badstr:
                            try:
                                if (
                                    to_mislabel_span_badstr[key][0] == int(v)
                                    and to_mislabel_span_badstr[key][1] > 0
                                ):
                                    badstr = "".join(
                                        random.choice(
                                            ";:,.{}@#!()^\/`[]+-|~`1234567890"
                                        )
                                        for _ in range(random.randint(1, 3))
                                    )
                                    db_hash[key] = badstr
                                    to_mislabel_span_badstr[key][1] -= 1
                                    to_mislabel_span_badstr[key][0] += 1
                                    if kwargs["verbose"]:
                                        print(
                                            "mislabeled: {}:{} to {}".format(
                                                k, v, badstr
                                            )
                                        )

                            except ValueError:
                                pass

                        if key in to_mislabel_span_integer:
                            try:
                                if (
                                    to_mislabel_span_integer[key][0] == int(v)
                                    and to_mislabel_span_integer[key][1] > 0
                                ):
                                    if to_mislabel_span_integer[key][2] == 0:
                                        to_mislabel_span_integer[key][2] = int(v) - 3
                                    db_hash[key] = to_mislabel_span_integer[key][2]
                                    to_mislabel_span_integer[key][1] -= 1
                                    to_mislabel_span_integer[key][2] += 1
                                    to_mislabel_span_integer[key][0] += 1
                                    if kwargs["verbose"]:
                                        print(
                                            "mislabeled: {}:{} to {}".format(
                                                k, v, to_mislabel_span_integer[key][2]
                                            )
                                        )
                            except ValueError:
                                pass

                    if cycling_fields:
                        for k, v in cycling_fields.items():
                            db_hash[k] = next(v)

                    if db_hash:
                        write_to_db.append(db_hash)
        to_miss = []
        while len(to_miss) < kwargs["structure_missing"]:
            to_miss.append(random.randint(0, len(write_to_db) - 1))

        # need to duplicate binary keys for ingest_as_binary
        to_duplicate = []
        while len(to_duplicate) < kwargs["structure_duplicate"]:
            to_duplicate.append(random.randint(0, len(write_to_db) - 1))

        for write_num, to_write in enumerate(write_to_db):
            if write_num in to_miss:
                to_miss.remove(write_num)
                if kwargs["verbose"]:
                    print("missing: ", write_num)
            else:
                db_key = "{}{}".format(kwargs["ingest_prefix"], str(uuid.uuid4()))
                redis_conn.hmset(db_key, to_write)
                time.sleep(kwargs["structure_stagger_delay"])
                if kwargs["verbose"]:
                    print(db_key)


def ingest_file(filename):
    file_bytes = b""
    try:
        with open(filename, "rb") as f:
            file_bytes = f.read()
    except Exception as ex:
        print(ex)
    return file_bytes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-host", default="127.0.0.1", help="db host ip")
    parser.add_argument("--db-port", default=6379, help="db port")
    parser.add_argument(
        "--db-prefix", default="glworb:", help="db key prefix, will be follwed by uuid"
    )
    parser.add_argument(
        "--db-expire-in", type=int, default=0, help="db key expiration time in seconds"
    )
    parser.add_argument(
        "--db-del-pattern",
        action="append",
        help="delete a pattern, will run before any other commands",
    )
    parser.add_argument(
        "--db-del-field",
        help="from --db-del-pattern pattern matches, only delete if specified field exists",
    )
    parser.add_argument(
        "--db-expire-interval", type=int, default=0, help="db key expiration interval"
    )

    parser.add_argument("--part-part-amounts", nargs="+", help="")
    parser.add_argument("--part-part-amounts-start", nargs="+", help="")
    parser.add_argument(
        "--part-increment-field", help="field to contain incrementing integers"
    )
    parser.add_argument(
        "--part-binary-field",
        default="binary_key",
        help="binary field name, will contain binary key",
    )
    parser.add_argument(
        "--part-binary-prefix",
        default="binary:",
        help="prefix for binary key, will be followed by uuid",
    )
    parser.add_argument(
        "--part-field-values",
        nargs="+",
        help="head is used as field name, tail for possible values",
    )
    parser.add_argument(
        "--field-cycle",
        action="append",
        nargs="+",
        help="field will be added to every part. possible values will cycle. head is used as field name, tail for possible values",
    )

    parser.add_argument("--structure-stagger-delay", type=float, default=0, help="")
    parser.add_argument("--structure-disorder", type=int, default=0, help="")
    parser.add_argument("--structure-duplicate", type=int, default=0, help="")
    parser.add_argument("--structure-missing", type=int, default=0, help="")

    parser.add_argument(
        "--binary-height", type=int, default=500, help="height of binary image"
    )
    parser.add_argument(
        "--binary-width", type=int, default=500, help="width of binary image"
    )

    parser.add_argument("--ingest-manifest", help="manifest file")
    parser.add_argument(
        "--ingest-manifest-lines",
        nargs="+",
        default=[],
        type=int,
        help="specific lines of manifest file to ingest. First line is 1, the header will be offset. Can be a sequence of integers",
    )
    parser.add_argument("--ingest-as-binary", nargs="+", default=[], help="")
    parser.add_argument(
        "--ingest-map",
        action="append",
        nargs=2,
        metavar=("source name", "destination name"),
        default=[],
        help="",
    )
    parser.add_argument("--ingest-prefix", default="glworb:", help="")
    parser.add_argument("--ingest-binary-prefix", default="binary:", help="")
    parser.add_argument(
        "--ingest-mislabel-span-integer",
        action="append",
        nargs=3,
        metavar=("field name", "span amount", "span max range"),
        default=[],
        help="mislabel span of a field",
    )
    parser.add_argument(
        "--ingest-mislabel-span-badstr",
        action="append",
        nargs=3,
        metavar=("field name", "span amount", "span max range"),
        default=[],
        help="mislabel span of a field",
    )

    parser.add_argument("--verbose", action="store_true", help="")

    args = vars(parser.parse_args())

    if args["ingest_manifest"] is not None:
        ingest_things(**args)
    else:
        generate_things(**args)


if __name__ == "__main__":
    main()
