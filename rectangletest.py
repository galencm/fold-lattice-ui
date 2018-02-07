# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2018, Galen Curwen-McAdams

from PIL import Image as PILImage, ImageDraw, ImageColor
import functools

def sequence_status(steps, filled, filename, width=60, height=120, step_offset=0, background_palette_field="",coloring=None):

    if coloring is None:
        coloring = {}

    # fallback color schemes
    # catch 'None' and '*' for everything else
    if not 'None' in coloring:
        coloring['None'] = {}
        coloring['None']['fill'] = "darkgray"
        coloring['None']['border'] = (135,135,135,1)
    else:
        if not 'fill' in coloring['None']:
            coloring['None']['fill'] = "darkgray"
        if not 'border' in coloring['None']:
            coloring['None']['border'] = (135,135,135,1)

    if not '*' in coloring:
        coloring['*'] = {}
        coloring['*']['fill'] = "lightgray"
        coloring['*']['border'] = (223,223,223,1)
    else:
        if not 'fill' in coloring['*']:
            coloring['*']['fill'] = "lightgray"

        if not 'border' in coloring['*']:
            coloring['*']['border'] = (223,223,223,1)

    status_tile = PILImage.new('RGB', (width, height), (155, 155, 155, 255))
    draw = ImageDraw.Draw(status_tile, 'RGBA')

    if len(filled) >= steps:
        sequence_steps = filled[:steps]
    else:
        sequence_steps = filled + [None for _ in range(steps - len(filled))]

    # use to set background
    draw_stack = []
    for step_num, step in enumerate(sequence_steps):

        if step is None:
            color = coloring['None']['fill']
            border_color = coloring['None']['border']
        else:
            color = coloring['*']['fill']
            border_color = coloring['*']['border']
            for k, v in coloring.items():
                for key, value in step.items():
                    if k == value:
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

                        stepwise = height / steps
                        x1 = 0
                        y1 = stepwise * step_num
                        x2 = width
                        y2 = (stepwise * step_num) + stepwise
                        #cell number label
                        draw_stack.append(functools.partial(draw.text, (x1, y1), str(step_num + step_offset), (230, 230, 230,128)))

                        if key == background_palette_field:
                            draw_call = functools.partial(draw.rectangle,(x1, y1, x2, y2), outline=border_color, fill=color)
                            draw_stack.insert(0, draw_call)
                        else:
                            # get rgb of color to modify alpha if needed
                            if isinstance(color,str):
                                color = ImageColor.getrgb(color)
                            draw_call = functools.partial(draw.rectangle,(x1, y1, x2, y2), outline=border_color, fill=color)
                            draw_stack.append(draw_call)
                        break
        # draw cells
        for dc in draw_stack:
            dc()

    image_filename = '/tmp/{}.jpg'.format(filename)
    status_tile.save(image_filename)
    status_tile.close()
    return image_filename
