# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2018, Galen Curwen-McAdams

import random
import io
import itertools
import redis
from collections import OrderedDict
import argparse
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
            cols: 2
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
        self.folded_fold_width = 40
        self.window_padding = 100
        self.window_width = 1000
        self.window_height = 600
        self.group_widgets = OrderedDict()
        # cli args
        if 'filter_key' in kwargs:
            self.filter_key = kwargs['filter_key']
        else:
            self.filter_key = "created"
        if 'group_amount' in kwargs:
            self.group_amount = kwargs['group_amount']
        else:
            self.group_amount = 5

        Window.size = (1000,800)
        super(AccordionContainer, self).__init__(anim_duration=0)

    def populate(self, *args):
        """Check for glworbs not in folds and
        add"""
        print("updating...")
        print("filtering by {}".format(self.filter_key))
        binary_keys = ["binary_key", "binary", "image_binary_key"]

        groups = list(group_into(self.group_amount, data_models.filter_data(filter_key=self.filter_key, pattern='glworb:*')))

        for group_num, group in enumerate(groups):
            if group not in self.groups:
                print("{new} not in groups".format(new=group))
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
                for glworb_num, glworb in enumerate(group):
                    if glworb:
                        keys = set(r.hgetall(glworb).keys())
                        for bkey in binary_keys:
                            data = r.hget(glworb, bkey)
                            if data:
                                print("{} has data".format(bkey))
                                break
                        try:
                            data = bimg_resized(data, self.resize_size)
                        except OSError:
                            data = None

                        if data:
                            fold_status.append(glworb)
                        else:
                            fold_status.append(None)
                            # generate a placeholder
                            placeholder = PImage.new('RGB', (self.resize_size, self.resize_size), (155, 155, 155, 1))
                            data_model_string =  data_models.pretty_format(r.hgetall(glworb), glworb)
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
                        group_container.image_grid.add_widget(img,
                                                              index=len(group_container.image_grid.children))

                        # Window.size = (img.texture_size[0] + self.window_padding,
                        #                img.texture_size[1] + self.window_padding)

                    group_container.keys = keys
                    group_container.glworbs = []#glworbs
                #sequence_status_img for thumbnails
                from rectangletest import sequence_status
                fold_status_image = sequence_status(len(group),
                                                    fold_status,
                                                    abs(hash(str(group))),
                                                    width=self.folded_fold_width,
                                                    height=self.resize_size,
                                                    step_offset=group_num*self.group_amount)
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
        if keycode[1] == 'left':
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
        elif keycode[1] == 'right':
            for i, c in enumerate(self.children):
                if c.collapse is False:
                    self.children[i-1].collapse = False
                    c.collapse = True
                    break
        elif keycode[1] == 'down' and not modifiers:
            for i, c in enumerate(self.children):
                if c.collapse is False:
                    c.thing.scroller.enlarge()
                    break
        elif keycode[1] == 'up' and not modifiers:
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

def bimg_resized(uuid, new_size):
    contents = binary_r.get(uuid)
    f = io.BytesIO()
    f = io.BytesIO(contents)
    img = PImage.open(f)
    img.thumbnail((new_size, new_size), PImage.ANTIALIAS)
    extension = img.format
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
    # python3 fold_lattice_ui.py -- --group-amount 20
    parser = argparse.ArgumentParser(description=tutorial_string,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--group-amount", type=int, help="group by",default=5)
    parser.add_argument("--filter-key",  help="filter by")
    args = parser.parse_args()

    FoldedInlayApp(**vars(args)).run()
