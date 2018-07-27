# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2018, Galen Curwen-McAdams

from textx.metamodel import metamodel_from_file
import os

path = os.path.dirname(os.path.realpath(__file__))
keyling_metamodel = metamodel_from_file(os.path.join(path, 'keyling.tx'))

# comma endings and quoting inspired by zeroscript:
# https://github.com/hintjens/zs
#
# (
# not [rotated],                # if source[rotated] does not exist or is None ![rotated]
# [device] == <capture1>,       # if source[device] equals 'capture1'
# $(img-pipe rotate 90 [*]),    # shell out command img-pip rotate source[META_DB_KEY]
# [rotated] = 90,               # set source[rotated] to 90
# )                             # write source values to db
#
# If any statements evaluate False, 
#   * break out of () block
#   * do not make any shell calls or write changes
#
# Notes:
#
# [*] is an alias for the db key to write to
# for now it will probably be the META_DB_KEY value
#
# strings are <"some string">  instead of <some string> until model is improved



def example():

    example_keyling_string = """
    (
    [rotated] not,
    [device] == <"capture1">,
    $(<"img-pipe rotate 90 [*]">),
    [rotated] = 90,
    )
    """

    l = keyling_metamodel.model_from_str(example_keyling_string)

    sources = [{"device" : "capture1", "META_DB_KEY" : "foo:1"},
               {"device" : "capture2", "rotated": 90, "META_DB_KEY" : "foo:2"}]

    for source in sources:
        source_writes = parse_lines(l, source, source["META_DB_KEY"])
        print(source_writes)

def model(text):
    model = keyling_metamodel.model_from_str(text)
    return model

def parse_lines(model, source, source_key, allow_shell_calls=False):
    calls = []
    for line in model.lines:
        if line.shellcall:
            call = line.shellcall.call.value.replace("[*]", source_key)
            calls.append(call)

        # name only
        if not line.symbol and not line.comparatee and not line.shellcall:
            if line.field.name in source:
                pass
            else:
                return None

        # name and symbol
        if line.symbol:
            symbol = line.symbol
            if symbol == "not" or symbol == "!":
                if not line.comparatee:
                    try:
                        if source[line.field.name]:
                            return None
                    except KeyError:
                        pass
            elif symbol == "==":
                if not line.field.name in source:
                    return None

                try:
                    comparatee = line.comparatee.value
                except:
                    comparatee = line.comparatee
                if source[line.field.name] == comparatee:
                    pass
                else:
                    return None
            elif symbol == "=":
                source.update({line.field.name : line.comparatee})

    for call in calls:
        if allow_shell_calls:
            print("calling: ",call)
    return source
