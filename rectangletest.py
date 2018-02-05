# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2018, Galen Curwen-McAdams

from PIL import Image as PILImage, ImageDraw

def sequence_status(steps, filled, filename, width=60, height=120, step_offset=0):

    status_tile = PILImage.new('RGB', (width, height), (155, 155, 155, 1))
    draw = ImageDraw.Draw(status_tile)

    if len(filled) >= steps:
        sequence_steps = filled[:steps]
    else:
        sequence_steps = filled + [None for _ in range(steps - len(filled))]

    for step_num, step in enumerate(sequence_steps):
        if step is None:
            color = "gray"
            border_color = (135,135,135,1)
        else:
            color = "lightgray"
            border_color = (223,223,223,1)
        stepwise = height / steps
        draw.rectangle((0, stepwise * step_num, width, (stepwise * step_num) + stepwise), outline=border_color, fill=color)

        draw.text((0, stepwise * step_num), str(step_num + step_offset), (230, 230, 230))

    image_filename = '/tmp/{}.jpg'.format(filename)
    status_tile.save(image_filename)
    status_tile.close()
    return image_filename
