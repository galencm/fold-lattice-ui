# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2018, Galen Curwen-McAdams

import random
import io
import itertools
import json
import redis
from collections import OrderedDict
import argparse
import functools
from PIL import Image as PImage

from kivy.app import App
from kivy.lang import Builder
from kivy.core.window import Window
from kivy.config import Config
from kivy.uix.scatter import Scatter
from kivy.uix.label import Label
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.textinput import TextInput
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import ListProperty, ObjectProperty
from kivy.graphics.vertex_instructions import (Rectangle,
                                               Ellipse,
                                               Line)
from kivy.graphics.context_instructions import Color
from kivy.uix.image import Image
from kivy.core.image import Image as CoreImage
from kivy.uix.behaviors import DragBehavior
from kivy.uix.button import Button
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.scrollview import ScrollView
from kivy.uix.recycleview import RecycleView
from kivy.uix.accordion import Accordion, AccordionItem
from kivy.clock import Clock

from ma_cli import data_models
#sequence_status_img for thumbnails
from rectangletest import sequence_status

r_ip, r_port = data_models.service_connection()
binary_r = redis.StrictRedis(host=r_ip, port=r_port)
r = redis.StrictRedis(host=r_ip, port=r_port, decode_responses=True)

Config.read('config.ini')
kv = """

<Selection>:
    #size:self.size
    #pos:self.pos
    size_hint:None,None
    border:1,1,1,1
    #background_color:1,1,1,0.5
    background_color:1,0,0,0.5
    background_normal:''
    # canvas:
    #     Color:
    #         rgba: 1, 0, 0, 0.25
    #     Rectangle:
    #         pos:self.pos
    #         size:self.size

<ScatterTextWidget>:
    id:image_container
    orientation: 'vertical'
    image_grid:image_grid
    scroller:scroller
    #float_layer:float_layer
    #size_hint:None,None
    ScrollViewer:
        canvas:
            Color:
                rgba: 1, 0, 0, 0.05
            Rectangle:
                pos: self.pos
                size: self.size
        #multitouch:False
        #size_hint:None,None
        #size_hint:1,1
        #size:self.size
        #height:self.parent.height
        id:scroller
        width:self.parent.width
        GridLayout:
            canvas:
                Color:
                    rgba: 0, 0, 0, 0.5
                Rectangle:
                    pos: self.pos
                    size: self.size
            #row_default_height: '1dp'
            #row_force_default: True
            id: image_grid
            #cols: 1
            rows: 1
            #size_hint:(None,None)
            size_hint_y: None
            size_hint_x:None
            #height: self.minimum_height
            #row_force_default:True
            #col_force_default:True
            #col_default_width:20
            size:self.parent.size
            spacing: 0, 0
            padding: 0, 0
            #size:800,800

"""

Builder.load_string(kv)

class AccordionItemThing(AccordionItem):
    def __init__(self, **kwargs):
        super(AccordionItemThing, self).__init__(**kwargs)
        self.thing = None

class AccordionContainer(Accordion):
    def __init__(self, **kwargs):
        self._keyboard = Window.request_keyboard(self._keyboard_closed, self)
        self._keyboard.bind(on_key_down=self._on_keyboard_down)
        self.groups = []
        self.resize_size = 600
        self.folded_fold_width = 44
        self.group_widgets = OrderedDict()
        self.palette = {}
        self.group_sketch = {}
        self.groups_to_show = {}
        self.subsort = "pagenum"
        # cli args
        if 'filter_key' in kwargs:
            self.filter_key = kwargs['filter_key']
        else:
            self.filter_key = "created"

        if 'group_amount' in kwargs:
            self.group_amount = kwargs['group_amount']
        else:
            self.group_amount = 5

        if 'palette' in kwargs:
            if isinstance(kwargs['palette'], dict):
                print(kwargs['palette'])
                self.palette = kwargs['palette']
                if 'palette_name' in kwargs:
                    if kwargs['palette_name']:
                        print("saving palette")
                        self.save_palette(kwargs['palette_name'], kwargs['palette'])

        if 'palette_name' in kwargs and kwargs['palette'] is None:
            self.palette = self.load_palette(kwargs['palette_name'])

        if 'group_sketch' in kwargs:
            if kwargs['group_sketch']:
                self.group_sketch = kwargs['group_sketch']

        if 'group_show' in kwargs:
            if kwargs['group_show']:
                self.groups_to_show = kwargs['group_show']

        super(AccordionContainer, self).__init__(anim_duration=0, min_space=self.folded_fold_width)

    def save_palette(self, palette_name, palette):
        """ Save a palette. Flatten the palette
        dictionary to store as redis hash"""
        flattened_palette = {}
        for category, colors in palette.items():
            for k,v in colors.items():
                if isinstance(v, tuple) or isinstance(v, list):
                    v = ",".join([str(s) for s in v])
                flattened_palette["{}____{}".format(category, k)] = v

        r.hmset("palette:{}".format(palette_name), flattened_palette)

    def load_palette(self, palette_name):
        """ Load a palette from redis.
        """
        unflattened_palette = {}
        palette = r.hgetall("palette:{}".format(palette_name))

        if palette:
            for k,v in palette.items():
                print(k,v)
                if "____" in k:
                    category, subkey = k.split("____")

                    if not category in unflattened_palette:
                        unflattened_palette[category] = {}

                    if not subkey in unflattened_palette[category]:
                        unflattened_palette[category][subkey] = ""

                    if "," in v:
                        v = tuple([int(s) for s in v.split(",")])

                    unflattened_palette[category][subkey] = v
            return unflattened_palette
        else:
            return {}

    def populate(self, *args):
        """Check for glworbs not in folds and
        add"""
        print("updating...")
        print("filtering by {}".format(self.filter_key))
        binary_keys = ["binary_key", "binary", "image_binary_key"]

        # dict({"chapter" : {"chapter1":60,"chapter2":60}})
        sketched_expiry = 1000
        sketched = {}

        for category in self.group_sketch.keys():
            if category == self.filter_key:
                for field_value, amount in self.group_sketch[category].items():
                    sketched[field_value] = {}
                    sketched[field_value]['amount'] = amount
                    sketched[field_value]['ids']  = []
                    for num in range(amount):
                        hash_name = "tmpsketch:{}:{}:{}".format(category, field_value, num)
                        r.hset(hash_name, category, field_value)
                        r.expire(hash_name, sketched_expiry)
                        sketched[field_value]['ids'].append(hash_name)

        glworbs = data_models.filter_data_to_dict(filter_key=self.filter_key, pattern='glworb:*', subsort=self.subsort)

        # use glworbs_reference to assert
        # that no glworbs are missing after
        # adding sketches
        glworbs_reference = []
        for k,v in glworbs.items():
            glworbs_reference.extend(v)

        glworbs_sketched_out = []

        for field_value in sketched.keys():
            try:
                sketch_amount = sketched[field_value]['amount'] - len(glworbs[field_value])
            except KeyError:
                sketch_amount = sketched[field_value]['amount']
                if not field_value in glworbs:
                    glworbs[field_value] = []
            if sketch_amount > 0:
                print("{} will be sketched out by {}".format(field_value, sketch_amount))
                glworbs[field_value].extend(sketched[field_value]['ids'][:sketch_amount])

        # sort dictionary by keyname
        for key in sorted(glworbs):
            if not self.groups_to_show or key in self.groups_to_show:
                glworbs_sketched_out.extend(glworbs[key])

        if not self.groups_to_show:
            assert set(glworbs_reference).issubset(set(glworbs_sketched_out))

        groups = list(group_into(self.group_amount, glworbs_sketched_out ))

        continuous_series = []
        continuous_mask = []
        for group_num, group in enumerate(groups):
            if group not in self.groups:
                # print("{new} not in groups".format(new=group))
                # a partial group may now have additional items.
                # Check if the first item matches and then
                # remove old partial widget and all
                # widgets after. Widgets will be repopulated
                # by new groups
                for i, g in enumerate(self.groups):
                    if group[0] == g[0]:
                        insertion_index = 0
                        for k, v in self.group_widgets.items():
                            if insertion_index >= i:
                                self.remove_widget(self.group_widgets[k])
                                del self.group_widgets[k]
                            insertion_index += 1

                group_container = ScatterTextWidget()
                fold_status = []
                widgets_to_add = []
                for glworb_num, glworb in enumerate(group):
                    if glworb:
                        glworb_values = r.hgetall(glworb)
                        keys = glworb_values.keys()
                        if self.subsort:
                            print(glworb_values)
                            try:
                                continuous_series.append(glworb_values[self.subsort])
                            except:
                                continuous_series.append(None)
                            try:
                                if len(continuous_series) == 1:
                                    continuous_mask.append(-1)
                                elif int(continuous_series[-2]) == int(continuous_series[-1]) - 1:
                                    continuous_mask[-1] = 0
                                    continuous_mask.append(0)
                                else:
                                    continuous_mask.append(-1)
                            except Exception as ex:
                                print(ex)
                                continuous_mask.append(None)
                        keys = set(glworb_values)
                        for bkey in binary_keys:
                            data = r.hget(glworb, bkey)
                            if data:
                                # print("{} has data".format(bkey))
                                break
                        try:
                            data = bimg_resized(data, self.resize_size, linking_uuid=glworb)
                        except OSError:
                            data = None

                        if data:
                            fold_status.append({"binary" : "data", self.filter_key : r.hget(glworb, self.filter_key)})
                        else:
                            fold_status.append({"binary" : "None", self.filter_key : r.hget(glworb, self.filter_key)})
                            # generate a placeholder
                            placeholder = PImage.new('RGB', (self.resize_size, self.resize_size), (155, 155, 155, 1))
                            data_model_string = data_models.pretty_format(r.hgetall(glworb), glworb)
                            # sketched will have no data
                            # use their id string instead
                            # sketched ids may or may not
                            # be unique
                            if not data_model_string:
                                data_model_string = glworb
                            placeholder = data_models.img_overlay(placeholder, data_model_string, 50, 50, 12)
                            file = io.BytesIO()
                            placeholder.save(file, 'JPEG')
                            placeholder.close()
                            file.seek(0)
                            data = file

                        img = ClickableImage(size_hint_y=None,
                                             size_hint_x=None,
                                             allow_stretch=True,
                                             keep_ratio=True)
                        img.texture = CoreImage(data, ext="jpg").texture
                        #widgets_to_add.append((img, index=len(group_container.image_grid.children))
                        widgets_to_add.append(functools.partial(group_container.image_grid.add_widget,img, index=len(group_container.image_grid.children)))
                    group_container.keys = keys

                for widget in widgets_to_add:
                    widget()

                fold_status_image = sequence_status(len(group),
                                                    fold_status,
                                                    abs(hash(str(group))),
                                                    width=self.folded_fold_width,
                                                    height=Window.size[1],
                                                    step_offset=group_num*self.group_amount,
                                                    background_palette_field=self.filter_key,
                                                    texturing=continuous_mask[group_num*self.group_amount:(group_num*self.group_amount)+glworb_num+1],
                                                    coloring=self.palette)
                fold_title = "{group_num} : {range_start} - {range_end}".format(group_num=str(group_num),
                                                                            range_start=group_num*self.group_amount,
                                                                            range_end=group_num*self.group_amount+glworb_num)
                fold = AccordionItemThing(title=fold_title,
                                          background_normal=fold_status_image,
                                          background_selected=fold_status_image)
                fold.thing = group_container
                fold.add_widget(group_container)
                self.add_widget(fold)
                self.group_widgets[str(group)] = fold

        self.groups = groups

    def _keyboard_closed(self):
        self._keyboard.unbind(on_key_down=self._on_keyboard_down)
        self._keyboard = None

    def _on_keyboard_down(self, keyboard, keycode, text, modifiers):
        print(keycode[1], modifiers)
        if keycode[1] == 'down' and 'shift' in modifiers:
            for i, c in enumerate(self.children):
                try:
                    c.thing.scroller.scroll_y -= (1/c.thing.image_grid.rows)
                except TypeError:
                    pass
        elif keycode[1] == 'up' and 'shift' in modifiers:
            for i, c in enumerate(self.children):
                try:
                    c.thing.scroller.scroll_y += (1/c.thing.image_grid.rows)
                except TypeError:
                    pass
        elif keycode[1] == 'left' and 'shift' in modifiers:
            for i, c in enumerate(self.children):
                try:
                    c.thing.scroller.scroll_x -= (1/len(c.thing.image_grid.children))
                except TypeError:
                    print(c.thing.image_grid.cols)
                    pass
        elif keycode[1] == 'right' and 'shift' in modifiers:
            for i, c in enumerate(self.children):
                try:
                    c.thing.scroller.scroll_x += (1/len(c.thing.image_grid.children))
                except TypeError:
                    print(c.thing.image_grid.cols)
                    pass
        elif keycode[1] == 'right' and 'ctrl' in modifiers:
            for i, c in enumerate(self.children):
                if c.thing.image_grid.rows is None:
                    if c.thing.image_grid.cols - 1 > 0:
                        c.thing.image_grid.cols -= 1
                elif c.thing.image_grid.cols is None:
                    if c.thing.image_grid.rows - 1 > 0:
                        c.thing.image_grid.rows -= 1
                print(c.thing.image_grid.rows,c.thing.image_grid.cols)
        elif keycode[1] == 'left' and 'ctrl' in modifiers:
            for i, c in enumerate(self.children):
                if c.thing.image_grid.rows is None:
                    c.thing.image_grid.cols += 1
                elif c.thing.image_grid.cols is None:
                    c.thing.image_grid.rows += 1
        elif keycode[1] == 'left' and 'z' in modifiers:
            if self.folded_fold_width - 5 > 0:
                self.folded_fold_width -= 5
                print(self.folded_fold_width)
            self.min_space = self.folded_fold_width
        elif keycode[1] == 'right' and 'z' in modifiers:
            self.folded_fold_width += 5
            print(self.folded_fold_width)
            self.min_space = self.folded_fold_width
        elif keycode[1] == 'left' and not modifiers:
            for i, c in enumerate(self.children):
                if c.collapse is False:
                    try:
                        self.children[i+1].collapse = False
                        c.collapse = True
                        break
                    except:
                        self.children[0].collapse = False
                        c.collapse = True
                        break
        elif keycode[1] == 'right' and not modifiers:
            for i, c in enumerate(self.children):
                if c.collapse is False:
                    self.children[i-1].collapse = False
                    c.collapse = True
                    break
        elif keycode[1] == 'up' and not modifiers:
            for i, c in enumerate(self.children):
                if c.collapse is False:
                    c.thing.scroller.enlarge()
                    break
        elif keycode[1] == 'down' and not modifiers:
            for i, c in enumerate(self.children):
                if c.collapse is False:
                    c.thing.scroller.shrink()
                    break
        elif keycode[1] == 'down' and 'ctrl' in modifiers:
            for i, c in enumerate(self.children):
                c.thing.scroller.enlarge()
        elif keycode[1] == 'up' and 'ctrl' in modifiers:
            for i, c in enumerate(self.children):
                c.thing.scroller.shrink()

class ClickableImage(Image):
    def __init__(self, **kwargs):
        super(ClickableImage, self).__init__(**kwargs)

    def on_touch_down(self, touch):
        if touch.button == 'left':
            if self.collide_point(touch.pos[0], touch.pos[1]):
                pass
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):

        if touch.button == 'right':
            p = touch.pos
            o = touch.opos
            s = min(p[0], o[0]), min(p[1], o[1]), abs(p[0] - o[0]), abs(p[1] - o[1])
            w = s[2]
            h = s[3]
            sx = s[0]
            sy = s[1]
            if abs(w) > 5 and abs(h) > 5:

                if self.collide_point(touch.pos[0], touch.pos[1]):
                    self.add_widget(Selection(pos=(sx, sy), size=(w, h)))
                    print("added widget for ", self)
                    print(self.texture_size, self.norm_image_size, self.size)
                    width_scale = self.texture_size[0] / self.norm_image_size[0]
                    height_scale = self.texture_size[1] / self.norm_image_size[1]
                    width_offset = (self.size[0] - self.norm_image_size[0]) / 2
                    print("touch", touch.pos, touch.opos)

                    # touch.push()
                    # touch.apply_transform_2d(self.to_local)
                    # #touch.apply_transform_2d(self.to_local)
                    # print("zzztouch",touch.pos,touch.opos)
                    # touch.pop()
                    print("window pos", self.to_window(*self.pos))

                    print("touch", touch.pos, touch.opos)
                    print("--------------")
        return super().on_touch_up(touch)

class ScrollViewer(ScrollView):
    #def on_scroll_move(self, *args,**kwargs):
    #    print(args)

    def enlarge(self, zoom_amount=2):
        for child in self.parent.image_grid.children:
            child.width *= zoom_amount
            child.height *= zoom_amount

    def shrink(self, zoom_amount=2):
        for child in self.parent.image_grid.children:
            print(child.size)
            child.width /= zoom_amount
            child.height /= zoom_amount

    def on_touch_down(self, touch):
        #print(">>",touch.button)
        #self.dispatch('on_test_event', touch)  # Some event that happens with on_touch_down
        #zoom_amount = 100
        zoom_amount = 2
        print(touch.button)
        if touch.button == 'left':
            return super().on_touch_down(touch)
        elif touch.button == 'scrollup':
            self.enlarge()
        elif touch.button == 'scrolldown':
            self.shrink()
    pass

class Selection(Button):
    def __init__(self, **kwargs):
        super(Selection, self).__init__(**kwargs)

    def on_press(self):
        print("pressed", self)
        self.parent.remove_widget(self)
        print("deleting self", self)
        del self
    #def on_release(self):
    #    print("release",self)

class ScatterTextWidget(BoxLayout):
    text_colour = ObjectProperty([1, 0, 0, 1])

    def __init__(self, **kwargs):
        super(ScatterTextWidget, self).__init__(**kwargs)
        self.image_grid.bind(minimum_height=self.image_grid.setter('height'),
                             minimum_width=self.image_grid.setter('width'))

    def change_label_colour(self, *args):

        colour = [random.random() for i in range(3)] + [1]
        self.text_colour = colour

    def on_touch_up(self, touch):

        if touch.button == 'right':
            p = touch.pos
            o = touch.opos
            s = min(p[0], o[0]), min(p[1], o[1]), abs(p[0] - o[0]), abs(p[1] - o[1])
            w = s[2]
            h = s[3]
            sx = s[0]
            sy = s[1]
            #only lower left to upper right works for clicking...
            #w and h have to both be positive
            if abs(w) > 5 and abs(h) > 5:
                if w < 0 or h < 0:
                    #self.float_layer.add_widget(Selection(pos=(abs(w), abs(h)), on_press=self.foo,size=touch.opos))
                    #self.float_layer.add_widget(Selection(pos=(abs(w), abs(h)),size=touch.opos))
                    ###self.float_layer.add_widget(Selection(pos=(sx,sy),size=(w, h)))
                    pass
                else:
                    #touch.pos  = p
                    #touch.opos = o
                    #min(p[0],o[0]), min(p[1],o[1]), abs(p[0]-o[0]), abs(p[1]-o[1])
                    ###self.float_layer.add_widget(Selection(pos=(sx,sy),size=(w, h)))
                    #self.float_layer.add_widget(Selection(pos=touch.opos, on_press=self.foo,size=(w, h)))
                    pass
        return super(ScatterTextWidget, self).on_touch_up(touch)

def group_into(n, iterable, fillvalue=None):
    args = [iter(iterable)] * n
    return itertools.zip_longest(fillvalue=fillvalue, *args)

def bimg_resized(uuid, new_size, linking_uuid=None):
    contents = binary_r.get(uuid)
    f = io.BytesIO()
    f = io.BytesIO(contents)
    img = PImage.open(f)
    img.thumbnail((new_size, new_size), PImage.ANTIALIAS)
    extension = img.format
    if linking_uuid:
        data_model_string = data_models.pretty_format(r.hgetall(linking_uuid), linking_uuid)
        # escape braces
        data_model_string = data_model_string.replace("{","{{")
        data_model_string = data_model_string.replace("}","}}")
        img = data_models.img_overlay(img, data_model_string, 50, 50, 12)
    file = io.BytesIO()
    img.save(file, extension)
    img.close()
    file.seek(0)
    #return file.getvalue()
    return file

class FoldedInlayApp(App):

    def __init__(self, *args, **kwargs):
        # store kwargs to passthrough
        self.kwargs = kwargs
        super(FoldedInlayApp, self).__init__()

    def build(self):

        root = AccordionContainer(orientation='horizontal',**self.kwargs)
        populate_interval = 10
        root.populate()
        Clock.schedule_interval(root.populate, populate_interval)
        return root

if __name__ == "__main__":
    tutorial_string = """
    """
    # kivy grabs argv, use a double dash
    # before argparse args
    # change grouping amount:
    #
    #     python3 fold_lattice_ui.py -- --group-amount 20
    #
    # change window size and create/save palette:
    #
    #     python3 fold_lattice_ui.py --size=1500x800  -- --filter-key source_uid \
    #     --palette '{"roman": { "border":"black", "fill": [155,155,255,1]}}' --palette-name foo
    #
    # visually sketch groups (values for field)
    # --group-sketch '{"chapter" : {"chapter1":60,"chapter2":60}}'

    parser = argparse.ArgumentParser(description=tutorial_string,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--group-amount", type=int, help="group by",default=5)
    parser.add_argument("--filter-key",  help="filter by")
    parser.add_argument("--palette-name",  help="palette to use")
    parser.add_argument("--palette", type=json.loads,  help="palette in json format, will be stored if --palette-name supplied")
    parser.add_argument("--group-sketch", type=json.loads,  help="create placeholders / expected to sketch out structure")
    parser.add_argument("--group-show", nargs='+', default=[], help="show only subset of groups")

    args = parser.parse_args()

    FoldedInlayApp(**vars(args)).run()
