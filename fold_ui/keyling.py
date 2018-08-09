# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2018, Galen Curwen-McAdams

from textx.metamodel import metamodel_from_file
import os
import subprocess
import shlex

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

def model(text):
    model = keyling_metamodel.model_from_str(text)
    return model

def parse_lines(model, source, source_key, allow_shell_calls=False, env_vars=None):
    calls = []
    if env_vars is None:
        env_vars = {}
    # include source keys as env vars by prefixing a $
    env_vars.update({"${}".format(k) : v for k, v in source.items()})

    for function in model.functions:
        for line in function.lines:
            if line.shellcall:
                if "NonBlockingShell" in str(line.shellcall):
                    call_mode = subprocess.Popen
                elif "BlockingShell" in str(line.shellcall):
                    call_mode = subprocess.call
                else:
                    call_mode = subprocess.Ccall
                call = line.shellcall.call.value.replace("[*]", source_key)
                # substitute env vars
                for var, var_value in env_vars.items():
                    call = call.replace(str(var), str(var_value))
                calls.append((call, call_mode))

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
                elif symbol == ">":
                    # currently only for ints
                    try:
                        comparatee = line.comparatee.value
                    except:
                        comparatee = line.comparatee

                    if int(source[line.field.name]) > int(comparatee):
                        pass
                    else:
                        return None
                elif symbol == "<":
                    # currently only for ints
                    try:
                        comparatee = line.comparatee.value
                    except:
                        comparatee = line.comparatee

                    if int(source[line.field.name]) < int(comparatee):
                        pass
                    else:
                        return None


    for call, call_mode in calls:
        if allow_shell_calls:
            print("calling: ",call, call_mode)
            print(call_mode(shlex.split(call)))
    return source

def example():

    example_keyling_strings = [
    """
    (
    [rotated] not,
    [device] == <"capture1">,
    $(<"img-pipe rotate 90 [*]">),
    [rotated] = 90,
    )
    """,

    """
    (
    [device] == <"capture1">,
    [equality] = 1,
    )
    """
    ]

    for script in example_keyling_strings:
        m = model(script)

        sources = [{"device" : "capture1", "META_DB_KEY" : "foo:1"},
                   {"device" : "capture2", "rotated": 90, "META_DB_KEY" : "foo:2"}]

        for source in sources:
            print(source)
            print(script)
            source_writes = parse_lines(m, source, source["META_DB_KEY"])
            print(source_writes)
            print("\n\n\n")
