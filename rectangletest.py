# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2018, Galen Curwen-McAdams

from PIL import Image as PILImage, ImageDraw

def sequence_status(steps, filled, filename, width=60, height=120, step_offset=0, coloring=None):

    if coloring is None:
        coloring = {}

    # fallback color schemes
    # catch 'None' and '*' for everything else
    if not 'None' in coloring:
        coloring['None'] = {}
        coloring['None']['fill'] = "gray"
        coloring['None']['border'] = (135,135,135,1)

    if not '*' in coloring:
        coloring['*'] = {}
        coloring['*']['fill'] = "lightgray"
        coloring['*']['border'] = (223,223,223,1)

    status_tile = PILImage.new('RGB', (width, height), (155, 155, 155, 1))
    draw = ImageDraw.Draw(status_tile)

    if len(filled) >= steps:
        sequence_steps = filled[:steps]
    else:
        sequence_steps = filled + [None for _ in range(steps - len(filled))]

    for step_num, step in enumerate(sequence_steps):

        if step is None:
            color = coloring['None']['fill']
            border_color = coloring['None']['border']
        else:
            color = coloring['*']['fill']
            border_color = coloring['*']['border']
            for k, v in coloring.items():
                if k == step:
                    try:
                        if isinstance(coloring[k]['fill'], list):
                            color = tuple(coloring[k]['fill'])
                        else:
                            color = coloring[k]['fill']
                    except Exception as ex:
                        print(ex)
                        color = coloring['*']['fill']

                    try:
                        if isinstance(coloring[k]['border'], list):
                            border_color = tuple(coloring[k]['border'])
                        else:
                            border_color = coloring[k]['border']
                    except Exception as ex:
                        print(ex)
                        border_color = coloring['*']['border']
                    break

        stepwise = height / steps
        draw.rectangle((0, stepwise * step_num, width, (stepwise * step_num) + stepwise), outline=border_color, fill=color)

        draw.text((0, stepwise * step_num), str(step_num + step_offset), (230, 230, 230))

    image_filename = '/tmp/{}.jpg'.format(filename)
    status_tile.save(image_filename)
    status_tile.close()
    return image_filename
