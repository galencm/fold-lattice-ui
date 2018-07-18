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
        redis_conn = redis.StrictRedis(host=kwargs["db_host"], port=kwargs["db_port"], decode_responses=True)

    if kwargs["db_del_pattern"]:
        for matched_key in redis_conn.scan_iter(match=kwargs["db_del_pattern"]):
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
    kwargs["part_part_amounts_start"] = [int(s) for s in kwargs["part_part_amounts_start"]]
    kwargs["part_part_amounts_start"] += [0] * (len(kwargs["part_part_amounts"]) - len(kwargs["part_part_amounts_start"]))


    to_disorder = kwargs["structure_disorder"]

    missed = 0
    duplicated = 0
    disordered = 0

    to_miss = []
    while len(to_miss) < kwargs["structure_missing"]:
        for part, amount in zip(field_values, kwargs["part_part_amounts"]):
            if len(to_miss) < kwargs["structure_missing"]:
                to_miss.append((random.randint(0, len(field_values) - 1),
                               random.randint(0, amount)))

    to_duplicate = []
    while len(to_duplicate) < kwargs["structure_duplicate"]:
        for part, amount in zip(field_values, kwargs["part_part_amounts"]):
            if len(to_duplicate) < kwargs["structure_duplicate"]:
                to_duplicate.append((random.randint(0, len(field_values) - 1),
                               random.randint(0, amount)))

    expire_interval = 0
    part_num = 0
    for part, amount, amount_start in zip(field_values, kwargs["part_part_amounts"], kwargs["part_part_amounts_start"]):
        print(part, part_num)
        duplicates = 1
        for sequence_number in range(amount):
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
                         thing[kwargs["part_increment_field"]] = sequence_number + amount_start
                    # add a binary field / key
                    if kwargs["part_binary_field"]:
                        db_binary_key =  kwargs["part_binary_prefix"] + str(uuid.uuid4())
                        thing[kwargs["part_binary_field"]] = db_binary_key
                        binary_bytes = generate_image(sequence_number, kwargs["binary_width"], kwargs["binary_height"])
                        binary_r.set(db_binary_key, binary_bytes)
                        if kwargs["db_expire_in"] > 0:
                            redis_conn.expire(db_binary_key, kwargs["db_expire_in"] + expire_interval)
                            expire_interval += kwargs["db_expire_interval"]

                        if kwargs["verbose"]:
                            print(db_binary_key)
                    things.append(thing)
            else:
                if kwargs["verbose"]:
                    print("missing:",(part_num, sequence_number))
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
        print("missed: {}\nduplicated: {}\ndisordered:{}".format(missed, duplicated, disordered))

def generate_image(text, width, height, background_color="lightgray"):

    img = PILImage.new('RGB', (width, height), background_color)
    draw = ImageDraw.Draw(img, 'RGBA')

    try:
        font = ImageFont.truetype("DejaVuSerif-Bold.ttf", 20)
    except Exception as ex:
        print(ex)
        font = None

    x =int(width / 2)
    y = int(height / 2)
    draw.text((x, y), str(text), fill="black", font=font)
    file = io.BytesIO()
    extension = 'JPEG'
    img.save(file, extension)
    img.close()
    file.seek(0)
    return file.getvalue()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-host",  help="db host ip")
    parser.add_argument("--db-port", default=6379, help="db port")
    parser.add_argument("--db-prefix",  default="glworb:", help="db key prefix, will be follwed by uuid")
    parser.add_argument("--db-expire-in", type=int, default=None, help="db key expiration time in seconds")
    parser.add_argument("--db-del-pattern", help="delete a pattern, will run before any other commands")
    parser.add_argument("--db-del-field", help="from --db-del-pattern pattern matches, only delete if specified field exists")
    parser.add_argument("--db-expire-interval", type=int, default=0, help="db key expiration interval")

    parser.add_argument("--part-part-amounts", nargs="+", help="")
    parser.add_argument("--part-part-amounts-start", nargs="+", help="")
    parser.add_argument("--part-increment-field", help="field to contain incrementing integers")
    parser.add_argument("--part-binary-field", default="binary_key", help="binary field name, will contain binary key")
    parser.add_argument("--part-binary-prefix", default="binary:", help="prefix for binary key, will be followed by uuid")
    parser.add_argument("--part-field-values", nargs="+", help="head is used as field name, tail for possible values")

    parser.add_argument("--structure-stagger-delay", type=float, default=0, help="")
    parser.add_argument("--structure-disorder", type=int, default=0, help="")
    parser.add_argument("--structure-duplicate", type=int, default=0, help="")
    parser.add_argument("--structure-missing", type=int, default=0, help="")

    parser.add_argument("--binary-height", type=int, default=500, help="height of binary image")
    parser.add_argument("--binary-width", type=int, default=500, help="width of binary image")

    parser.add_argument("--verbose", action="store_true", help="")

    args = vars(parser.parse_args())
    generate_things(**args)

if __name__ == "__main__":
    main()