# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2018, Galen Curwen-McAdams

from PIL import Image as PILImage, ImageDraw

def sequence_status(steps, filled, filename, width=60, height=120):

    status_tile = PILImage.new('RGB', (width, height), (155, 155, 155, 1))
    draw = ImageDraw.Draw(status_tile)

    for step_num, step in enumerate(filled[:steps]):
        if step is None:
            color = "gray"
        else:
            color = "white"
        stepwise = height / steps
        draw.rectangle((0, stepwise * step_num, width, (stepwise * step_num) + stepwise), outline=None, fill=color)

    image_filename = '/tmp/{}.jpg'.format(filename)
    status_tile.save(image_filename)
    status_tile.close()
    return image_filename
