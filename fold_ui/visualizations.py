# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2018, Galen Curwen-McAdams

from PIL import Image as PILImage, ImageDraw, ImageColor, ImageFont
import functools
import operator
import io
import uuid
import math
from collections import OrderedDict

@functools.lru_cache()
def calculate_fontsize(text, fontsize, width):
    try:
        font = ImageFont.truetype("DejaVuSerif-Bold.ttf", fontsize)
    except Exception as ex:
        print(ex)
        font = None

    while font.getsize(text)[0] > width:
        fontsize -= 1
        try:
            font = ImageFont.truetype("DejaVuSerif-Bold.ttf", fontsize)
        except Exception as ex:
            print(ex)
            font = None
    return font, fontsize

def vertical_texture(draw, spacing, top, height, width):
    # draw mutable, so no return
    for space in range(0, width, round(width / spacing)):
        draw.line((space, top, space, top + height), width=2, fill=(255, 255, 255, 128))

def structure_preview(structure, spec, palette, sparse_expected=False, sparse_found_from_zero=False, sparse_found=False, start_offset=False, only_possible=False, ragged=False, ragged_sub=False, cell_width=None, cell_height=None, column_slots=None, cell_scale=.25, background_color=(155, 155, 155, 255), filename=None, return_columns=False, **kwargs):

    if cell_width is None:
        cell_width = 15

    if cell_height is None:
        cell_height = 30

    if column_slots is None:
        column_slots = 10

    specs = {}
    specs[None] = {}

    overall_structure = {}

    ordering = {p.name : p.order_value for p in palette}

    expected = {}
    for p in palette:
        for possiblity in p.possibilities:
            expected[possiblity.name] = possiblity.rough_amount
            #possiblity.rough_start
            #possiblity.rough_end

    for s in spec:
        specs[s.primary_layout_key] = s
        overall_structure[s.primary_layout_key] = []

    cells = []
    subsorted_cells = []

    # allocate slots for broad structure by primary_keys
    # allocate / subsort if needed
    matched = []
    for cell in structure:
        for k, v in cell.items():
            for s in spec:
                if s.primary_layout_key == k:
                    if only_possible:
                        if cell[k] in [possiblity.name for possiblity in p.possibilities for p in palette if p.name == k]:
                            overall_structure[k].append(cell)
                            matched.append(cell)
                    else:
                        overall_structure[k].append(cell)
                        matched.append(cell)

    for s in spec:
        try:
            # get subsort_key for sparse_expected
            # a integer/floating value is needed to allocate
            # sparse positions using rough amounts
            # assumes that primary_layout_key field contains string values
            # rather than integers
            if sparse_expected:
                subsort_key = None
                for key, area in sorted(s.cell_layout_meta["sortby"]):
                    if key != s.primary_layout_key:
                        subsort_key = key
                if subsort_key is None:
                    subsort_key = s.primary_layout_key

            for key, area in sorted(s.cell_layout_meta["sortby"]):
                try:
                    overall_structure[s.primary_layout_key].sort(key=operator.itemgetter(key))

                    if ragged_sub:
                        if key == s.primary_layout_key:
                            prev = None
                            items = 0
                            to_insert = []
                            for i, item in enumerate(overall_structure[s.primary_layout_key]):
                                if item:
                                    if prev != item[key] and prev != None:
                                        to_pad =  column_slots - (items % column_slots)
                                        items = -1
                                        if to_pad == column_slots:
                                            to_pad = 0
                                        for _ in range(to_pad):
                                            try:
                                                overall_structure[s.primary_layout_key].insert(i, None)
                                            except:
                                                pass
                                    items += 1
                                    prev = item[key]
                            to_pad = column_slots - (items % column_slots)
                            if to_pad == column_slots:
                                to_pad = 0
                            for _ in range(to_pad):
                                try:
                                    overall_structure[s.primary_layout_key].append(None)
                                except:
                                    pass

                    if sparse_expected:
                        # only run with s.primary_layout_key
                        # to get correct initial ordering
                        if key == s.primary_layout_key:
                            sublists = OrderedDict()
                            for item in overall_structure[s.primary_layout_key]:
                                if not item[key] in sublists:
                                    sublists[item[key]] = []
                                sublists[item[key]].append(item)

                            sparse = []
                            rough_start_offset = 0
                            for k, v in sublists.items():
                                sparse_expected = []
                                if k in expected:
                                    if start_offset is True:
                                        rough_start_offset += expected[k] + 1
                                    sparse_expected = [None] * expected[k]
                                    for item in v:
                                        try:
                                            if isinstance(item[subsort_key], int):
                                                try:
                                                    if sparse_expected[item[subsort_key] - rough_start_offset] is None:
                                                        sparse_expected[item[subsort_key] - rough_start_offset] = item
                                                    else:
                                                        sparse_expected.insert(item[subsort_key] - rough_start_offset, item)
                                                except IndexError:
                                                    sparse_expected.insert(item[subsort_key] - rough_start_offset, item)
                                            else:
                                                sparse_expected.remove(None)
                                                sparse_expected.insert(0, item)
                                        except Exception as ex:
                                            sparse_expected.remove(None)
                                            sparse_expected.insert(0, item)
                                else:
                                    sparse_expected = v
                                sparse.extend(sparse_expected)

                            overall_structure[s.primary_layout_key] = sparse

                    if sparse_found_from_zero or sparse_found:
                        try:
                            print(sparse_found, sparse_found_from_zero)
                            sparse_found_begin = overall_structure[s.primary_layout_key][0][key]
                            sparse_found_end = overall_structure[s.primary_layout_key][-1][key]
                            # None's from 0 position?
                            #sparse_found = [None] * (sparse_found_end - sparse_found_begin)
                            sparse_found_padded = [None] * (sparse_found_end + 1)

                            for i, item in enumerate(overall_structure[s.primary_layout_key]):
                                sparse_found_padded.insert(int(item[key]), item)

                            if sparse_found_from_zero or sparse_found:
                                # prune trailing None's
                                while sparse_found_padded and sparse_found_padded[-1] is None:
                                    sparse_found_padded.pop()

                            if sparse_found:
                                # prune leading Nones
                                print("pruning leading")
                                while sparse_found_padded and sparse_found_padded[0] is None:
                                    sparse_found_padded.pop(0)

                            overall_structure[s.primary_layout_key] = sparse_found_padded
                        except Exception as ex:
                            print(ex)
                except Exception as ex:
                    print(ex)
        except Exception as ex:
            print(ex)

    sorted_cells = []
    # print(ordering, overall_structure.keys())
    ordering = sorted(ordering.items(), key=lambda kv: kv[1])

    if ragged:
        for k, v in overall_structure.items():
            to_pad = len(v) % column_slots
            for _ in range(to_pad):
                overall_structure[k].extend([None])

    for k, _ in ordering:
        try:
            print("adding {}".format(k))
            sorted_cells.extend(overall_structure[k])
        except KeyError as ex:
            print(ex)
            pass
    # for k, v in overall_structure.items():
    #     sorted_cells.extend(v)
    unmatched = [cell for cell in structure if not cell in matched]

    # for crude implementation of continuity
    # see notes below
    continuity_previous = None
    continuity_current = None
    continuity_key = None
    primary_previous = None
    annotations = []

    for cell_position, cell in enumerate(sorted_cells):
        cell_textures = []
        try:
            for k, v in cell.items():
                for s in spec:
                    if s.primary_layout_key == k:
                        # crude implementation of continuity:
                        #
                        # part of a rough set of annotations that can
                        # be used to draw attention or control the automatic
                        # artifacting of some sources if everything looks good
                        #
                        # the annotations would at least include:
                        # continuous / discontinuous
                        # duplicate
                        # too few (based on rough amount)
                        # too many (based on rough amount)
                        try:
                            if s.cell_layout_meta["continuous"]:
                                for keyname, _ in s.cell_layout_meta["continuous"]:
                                    continuity_key = keyname
                        except KeyError:
                            pass
                        try:
                            continuity_previous = continuity_current
                            continuity_current = cell[continuity_key]
                            if continuity_current - 1 != continuity_previous and cell[k] == primary_previous:
                                annotations.append(("discontinuous", continuity_key, cell_position, cell_position - 1))
                                cell_textures.append("discontinuous")
                            primary_previous = cell[k]
                        except KeyError:
                            pass

                        cells.append(cell_preview(s, cell, meta=s.cell_layout_meta, width=cell_width, height=cell_height, textures=cell_textures)[1:])
        except AttributeError:
            # a padding None
            cells.append(cell_preview(None, None, meta=None, width=cell_width, height=cell_height)[1:])

    for cell in unmatched:
        cells.append(cell_preview(None, None, meta=None, width=cell_width, height=cell_height)[1:])

    if return_columns is True:
        total_width = cell_width
        total_height = int(column_slots * cell_height)
        if not total_width:
            total_width = 1

        cell_start = 0
        columns = []
        for col in range(math.ceil(len(cells)/column_slots)):
            column_cells = []
            img = PILImage.new('RGB', (total_width, total_height), background_color)
            draw = ImageDraw.Draw(img, 'RGBA')
            x =0
            y = 0
            row_pos = 0
            for cell, cell_source in cells[cell_start:cell_start + column_slots]:
                column_cells.append(cell_source)
                c = PILImage.open(cell)
                img.paste(c, (x, y))
                row_pos += 1
                y += cell_height
            cell_start += column_slots
            filename = True
            if filename:
                image_filename = '/tmp/{}.jpg'.format(str(uuid.uuid4()))
                img.save(image_filename)
                filename = image_filename
            #img.show()
            file = io.BytesIO()
            extension = 'JPEG'
            img.save(file, extension)
            img.close()
            file.seek(0)
            columns.append((filename, file, column_cells))
        #return (filename, file)
        return columns
    else:
        total_width = math.ceil(len(cells)/column_slots) * cell_width
        total_height = int(column_slots * cell_height)

        if not total_width:
            total_width = 1

        #print("structure_preview", structure, spec, palette, cells, total_width, total_height)

        img = PILImage.new('RGB', (total_width, total_height), background_color)
        draw = ImageDraw.Draw(img, 'RGBA')
        x =0
        y = 0
        row_pos = 0
        for cell, cell_source in cells:
            c = PILImage.open(cell)
            img.paste(c, (x, y))
            # print(i, x, y)
            if row_pos == (column_slots - 1):
                row_pos = 0
                x += cell_width
                y = 0
            else:
                row_pos += 1
                y += cell_height

        if filename:
            image_filename = '/tmp/{}.jpg'.format(str(uuid.uuid4()))
            img.save(image_filename)
            filename = image_filename
        # img.show()
        file = io.BytesIO()
        extension = 'JPEG'
        img.save(file, extension)
        img.close()
        file.seek(0)

        return (filename, file)

def cell_preview(spec, cell=None, meta=None, width=60, height=120, cells=1, margins=None, default_margin=5, regions=None, palette=None, background_color=(155, 155, 155, 255), overlay_placeholders=False, textures=None, filename=None):

    if textures is None:
        textures = []

    try:
        margins = spec.cell_layout_margins
    except:
        pass

    # default colors used if spec and cell are None
    palette_map = dict({
                       "top": "lightgray",
                       "bottom": "darkgray",
                       "left": "lightgray",
                       "right": "darkgray",
                       "center": "gray"
                      })

    try:
        palette_map.update(spec.palette_map)
    except AttributeError as ex:
        #print(ex)
        pass

    if margins is None:
        margins = {}

    margin_names = ("top", "bottom", "left", "right")

    for margin_name in margin_names:
        if not margin_name in margins:
            margins[margin_name] = default_margin

    if regions is None:
        regions = {}

    if palette is None:
        palette = {}

    def cell_top(region_margin=margins["top"], x=0, y=0):
        return (x, y, x + width, y + region_margin)

    def cell_bottom(region_margin=margins["bottom"], x=0, y=0):
        return (x, y + height - region_margin, x + width, y + height)

    def cell_left(region_margin=margins["left"], x=0, y=0):
        return (x, y, x + region_margin, y + height)

    def cell_right(region_margin=margins["right"], x=0, y=0):
        return (x + width -region_margin, y, x + width, y + height)

    def cell_center(region_margin=margins, x=0, y=0):
        return (x + region_margin["left"], y + region_margin["top"], x + width - region_margin["right"], y + height - region_margin["bottom"])

    img = PILImage.new('RGB', (width, height * cells), background_color)
    draw = ImageDraw.Draw(img, 'RGBA')

    cell_y_offset = 0
    for _ in range(cells):
        meta_calls = []
        for region, color in palette_map.items():
            if region == "top":
                call = cell_top
            elif region == "bottom":
                call = cell_bottom
            elif region == "left":
                call = cell_left
            elif region == "right":
                call = cell_right
            elif region == "center":
                call = cell_center

            if cell:
                # try to override color here
                # for k, v in spec.cell_layout_map.items():
                #{'top': None, 'bottom': None, 'left': None, 'right': None, 'center': 'c'}
                #[PaletteThing(name='c', possibilities=[ColorMapThing(color=<Color #9017f0>, name='c1', rough_amount=12)], color=<Color #1648e0>)]
                key_name = spec.cell_layout_map[region]
                try:
                    value = cell[key_name]
                    for palette_thing in spec.palette():
                        if palette_thing.name == key_name:
                            for possiblity in palette_thing.possibilities:
                                if possiblity.name == value:
                                    color = possiblity.color.hex_l
                except Exception as ex:
                    # print(ex)
                    # print(spec.cell_layout_map)
                    # print(cell)
                    pass

            try:
                draw.rectangle(call(y=cell_y_offset),fill=color)
            except Exception as ex:
                pass

            try:
                #print(spec.cell_layout_meta.items(), spec.cell_layout_map.items())
                for meta, field_names in  spec.cell_layout_meta.items():
                    for field_name, field_area in field_names:
                        for k, v in spec.cell_layout_map.items():
                            if v == field_name:
                                if k == region:
                                    if field_area == region:
                                        if meta == "overlay":
                                            try:
                                                text = str(cell[field_name])
                                            except:
                                                if overlay_placeholders is True:
                                                    text = str(field_name)
                                                else:
                                                    # catch in outer exception
                                                    text = str(cell[field_name])
                                            font, fontsize = calculate_fontsize(text, 20, width)
                                            text_width, text_height = draw.textsize(text, font=font)
                                            text_x_offset = 0
                                            text_y_offset = 0
                                            if region == "right":
                                                text_x_offset = (-1 * text_width)
                                            elif region == "top":
                                                text_y_offset = int((1 * text_height) / 2)
                                            elif region == "bottom":
                                                text_y_offset = (-1 * text_height)
                                            meta_calls.append(functools.partial(draw.text, call(y=cell_y_offset+text_y_offset,x=text_x_offset)[:2], text, fill="black", font=font))
            except Exception as ex:
                pass

        # draw textures before meta_calls so
        # text overlays will be drawn last
        # discontinuous currently draws in center only
        for texture in textures:
            if texture == "discontinuous":
                dy = 0
                bar_width = 1
                x1, y1, x2, y2 = cell_center()
                for height_step in range(y1, y2, bar_width * 8):
                    draw.rectangle((0, height_step, width, height_step + bar_width), fill="white")

        for meta_call in meta_calls:
            meta_call()

        cell_y_offset += height


    if filename:
        image_filename = '/tmp/{}.jpg'.format(str(uuid.uuid4()))
        img.save(image_filename)
        filename = image_filename

    file = io.BytesIO()
    extension = 'JPEG'
    img.save(file, extension)
    img.close()
    file.seek(0)

    return (filename, file, cell)

def sequence_status(steps, filled, filename, width=60, height=120, step_offset=0, background_palette_field="", texturing=None, coloring=None):

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
        if texturing:
            try:
                if texturing[step_num] == 0:
                    # continuous draw vertical lines
                    draw_stack.append(functools.partial(vertical_texture, draw, 8, y1, stepwise, width))
                elif texturing[step_num] == -1:
                    # discontinuous
                    pass
            except IndexError:
                pass
        # draw cells
        for dc in draw_stack:
            dc()

    image_filename = '/tmp/{}.jpg'.format(filename)
    status_tile.save(image_filename)
    status_tile.close()
    return image_filename
