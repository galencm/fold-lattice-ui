# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2018, Galen Curwen-McAdams

import random
import io
import random
import itertools
import os
import json
import redis
from collections import OrderedDict
import atexit
import inspect
import sys
import argparse
import functools
import fnmatch
import uuid
import colour
from PIL import Image as PImage
from lxml import etree
import attr

from kivy.app import App
from kivy.lang import Builder
from kivy.core.window import Window
from kivy.config import Config
from kivy.uix.scatter import Scatter
from kivy.uix.label import Label
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.textinput import TextInput
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.checkbox import CheckBox
from kivy.uix.dropdown import DropDown
from kivy.uix.popup import Popup
from kivy.uix.colorpicker import ColorPicker
from kivy.properties import ListProperty, ObjectProperty, BooleanProperty
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
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.clock import Clock

from ma_cli import data_models
#sequence_status_img for thumbnails
from fold_ui.rectangletest import sequence_status, cell_preview, structure_preview
import fold_ui.bindings as bindings

r_ip, r_port = data_models.service_connection()
binary_r = redis.StrictRedis(host=r_ip, port=r_port)
redis_conn = redis.StrictRedis(host=r_ip, port=r_port, decode_responses=True)

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

class DropDownInput(TextInput):

    def __init__(self, preload=None, preload_attr=None, preload_clean=True, **kwargs):
        self.multiline = False
        self.drop_down = DropDown()
        self.drop_down.bind(on_select=self.on_select)
        self.bind(on_text_validate=self.add_text)
        self.preload = preload
        self.preload_attr = preload_attr
        self.preload_clean = preload_clean
        self.not_preloaded = set()
        super(DropDownInput, self).__init__(**kwargs)
        self.add_widget(self.drop_down)

    def add_text(self,*args):
        if args[0].text not in [btn.text for btn in self.drop_down.children[0].children if hasattr(btn ,'text')]:
            btn = Button(text=args[0].text, size_hint_y=None, height=44)
            self.drop_down.add_widget(btn)
            btn.bind(on_release=lambda btn: self.drop_down.select(btn.text))
            if not 'preload' in args:
                self.not_preloaded.add(btn)

    def on_select(self, *args):
        self.text = args[1]
        if args[1] not in [btn.text for btn in self.drop_down.children[0].children if hasattr(btn ,'text')]:
            self.drop_down.append(Button(text=args[1]))
            self.not_preloaded.add(btn)
        # call on_text_validate after selection
        # to avoid having to select textinput and press enter
        self.dispatch('on_text_validate')

    def on_touch_down(self, touch):
        preloaded = set()
        if self.preload:
            for thing in self.preload:
                if self.preload_attr:
                    # use operator to allow dot access of attributes
                    thing_string = str(operator.attrgetter(self.preload_attr)(thing))
                else:
                    thing_string = str(thing)
                self.add_text(Button(text=thing_string),'preload')
                preloaded.add(thing_string)

        # preload_clean removes entries that
        # are not in the preload source anymore
        if self.preload_clean is True:
            added_through_widget = [btn.text for btn in self.not_preloaded if hasattr(btn ,'text')]
            for btn in self.drop_down.children[0].children:
                try:
                    if btn.text not in preloaded and btn.text not in added_through_widget:
                        self.drop_down.remove_widget(btn)
                except Exception as ex:
                    pass

        return super(DropDownInput, self).on_touch_down(touch)

    def on_touch_up(self, touch):
        if touch.grab_current == self:
            self.drop_down.open(self)
        return super(DropDownInput, self).on_touch_up(touch)

class ColorPickerPopup(Popup):
    def __init__(self, **kwargs):
        self.title = "foo"
        self.content = ColorPicker()
        self.size_hint = (.5,.5)
        super(ColorPickerPopup, self).__init__()

@attr.s
class PaletteThing(object):
    name = attr.ib(default=None)
    # list of ColorMapThing s
    possibilities = attr.ib(default=attr.Factory(list))
    color = attr.ib(default=None)
    order_value = attr.ib(default=1.0)

    @name.validator
    def check_name(self, attribute, value):
        if value is None:
            setattr(self, 'name', str(uuid.uuid4()).replace("-","_"))

    @color.validator
    def check_color(self, attribute, value):
        if not value:
            setattr(self,'color', colour.Color(pick_for=self))

@attr.s
class ColorMapThing(object):
    color = attr.ib(default=None)
    name =  attr.ib(default=None)
    rough_amount =  attr.ib(default=0)
    order_value = attr.ib(default=1.0)

    @color.validator
    def check_color(self, attribute, value):
        if not value:
            setattr(self,'color', colour.Color(pick_for=self))

    @name.validator
    def check_name(self, attribute, value):
        if value is None:
            setattr(self, 'name', str(uuid.uuid4()).replace("-","_"))

@attr.s
class CellSpec(object):
    # part this spec applies to
    spec_for = attr.ib(default=None)
    # layout field to use for classification
    primary_layout_field = attr.ib(default="center")

    @property
    def primary_layout_key(self):
        return self.cell_layout_map[self.primary_layout_field]

    @spec_for.validator
    def check_spec_for(self, attribute, value):
        if value is None:
            setattr(self, 'spec_for', str(uuid.uuid4()).replace("-","_"))

    # get palette from elsewhere ?
    # or dict:
    # thing_name : color
    palette = attr.ib(default=attr.Factory(dict))
    amount = attr.ib(default=attr.Factory(dict))

    # dict:
    # top : some_thing_name
    # bottom : some_thing_name
    # left : some_thing_name
    # right : some_thing_name
    cell_layout_map = attr.ib(default=None)

    # tuple (top, bottom, left, right)
    cell_layout_margins = attr.ib(default=attr.Factory(dict))

    cell_layout_meta = attr.ib(default=attr.Factory(dict))

    @palette.validator
    def check_Palette(self, attribute, value):
        if not value:
            setattr(self,'palette', dict({
                                          "default" : colour.Color(pick_for=self)
                                          }))

    @cell_layout_map.validator
    def check_layout_map(self, attribute, value):
        if value is None or not value:
            setattr(self,'cell_layout_map', dict({
                                           "top": None,
                                           "bottom": None,
                                           "left": None,
                                           "right": None,
                                           "center": None
                                          }))
    @property
    def palette_map(self):
        palettes = self.palette()
        mapped = {}
        for layout_name, part_name in self.cell_layout_map.items():
            mapped[layout_name] = None
            for palette in palettes:
                if palette.name == part_name:
                    mapped[layout_name] = palette.color.hex_l

        return mapped

class CellSpecContainer(BoxLayout):
    def __init__(self, **kwargs):
        self.app = None
        super(CellSpecContainer, self).__init__(**kwargs)

    def spec(self):
        specs = []
        for cell_spec in self.children:
            specs.append(cell_spec.cell_spec)
        return specs

    def add_cell_spec(self, cell_spec):
        #cell_spec.height = 44
        #cell_spec.size_hint_y = None
        self.add_widget(cell_spec)
        self.parent.scroll_to(cell_spec)

    def remove_cell_spec(self, cell_spec_id):
        for cell_spec in self.children:
            try:
                if cell_spec == cell_spec_id:
                    del cell_spec.cell_spec
                    self.remove_widget(cell_spec)
            except AttributeError as ex:
                pass

    def generate_previews(self):
        for cell_spec in self.children:
            try:
                cell_spec.generate_preview()
            except AttributeError as ex:
                pass
        # update structure preview image
        self.app.session['structure'].generate_structure_preview(parameters=self.app.session['structure'].parameters)

    def generate_structure(self):
        self.app.session['structure'].generate_structure_preview(parameters=self.app.session['structure'].parameters)

class CellSpecItem(BoxLayout):
    def __init__(self, cell_spec, **kwargs):
        self.cell_spec = cell_spec
        self.cells_preview = Image(size_hint_x=None)
        self.meta_widgets = []
        super(CellSpecItem, self).__init__(**kwargs)
        preview_box = BoxLayout(orientation="vertical", size_hint_x=None)
        preview_box.add_widget(self.cells_preview)
        cell_delete = Button(text="del", height=30, size_hint_y=1, size_hint_x=None)
        cell_delete.bind(on_press=lambda widget: self.parent.remove_cell_spec(self))
        self.add_widget(cell_delete)
        # subsort here?
        self.add_widget(preview_box)
        self.generate_cell_layout_widgets()
        self.init_meta()
        self.generate_preview()

    def set_name(self, name):
        self.cell_spec.spec_for = name

    def init_meta(self):
        # set checkboxs to correct state on init
        # important for restoring session from xml
        for k, v in self.cell_spec.cell_layout_meta.items():
            if v:
                for _, area in v:
                    for w in self.meta_widgets:
                        if k == w.meta_option and w.meta_option_area == area:
                            w.active = BooleanProperty(True)

    def set_meta(self, widget, value):
        if value:
            if widget.meta_option == "primary":
                self.cell_spec.primary_layout_field = widget.meta_option_area
                # this should uncheck all other primary checkboxes, but does not
                try:
                    for w in widget.similar:
                        if w != widget:
                            if w.active:
                                w.active = BooleanProperty(False)
                except Exception as ex:
                    print(ex)
                    pass

            if not widget.meta_option in self.cell_spec.cell_layout_meta:
                self.cell_spec.cell_layout_meta[widget.meta_option] = []
            if not (widget.meta_option_value.text,  widget.meta_option_area) in self.cell_spec.cell_layout_meta[widget.meta_option]:
                self.cell_spec.cell_layout_meta[widget.meta_option].append((widget.meta_option_value.text,  widget.meta_option_area))
        else:
            try:
                self.cell_spec.cell_layout_meta[widget.meta_option].remove((widget.meta_option_value.text,  widget.meta_option_area))
            except:
                pass
        # wrap in try/except to prevent error before
        # widget has a parent
        try:
            self.parent.generate_structure()
        except AttributeError:
            pass

    def generate_cell_layout_widgets(self):
        rows =  BoxLayout(orientation="vertical", size_hint_x=1)
        similar={}
        meta_widgets = []
        for area in ["top", "bottom", "left", "right", "center"]:
            row = BoxLayout(orientation="horizontal", height=30, size_hint_y=None, size_hint_x=1)
            row.add_widget(Label(text=area))
            things = TextInput(multiline=False)
            try:
                if self.cell_spec.cell_layout_map[area]:
                    things.text = str(self.cell_spec.cell_layout_map[area])
            except KeyError:
                pass
            things.bind(on_text_validate=lambda widget, area=area: self.set_layout_region(area, widget.text))
            margin = TextInput(multiline=False)
            margin.margin_for = area
            try:
                if self.cell_spec.cell_layout_margins[area]:
                    margin.text = str(self.cell_spec.cell_layout_margins[area])
            except KeyError:
                pass
            margin.bind(on_text_validate=lambda widget: self.set_margin(widget.margin_for, widget.text, widget))
            row.add_widget(things)
            row.add_widget(Label(text="margin"))
            row.add_widget(margin)

            # meta options
            for meta_option in ["primary", "sortby", "continuous", "overlay"]:
                if not meta_option in similar:
                    similar[meta_option] = []
                meta_toggle = CheckBox()
                meta_toggle.meta_option = meta_option
                meta_toggle.meta_option_value = things
                meta_toggle.meta_option_area = area
                meta_toggle.bind(active=self.set_meta)
                if meta_option == "primary" and meta_toggle.meta_option_area == self.cell_spec.primary_layout_field:
                    meta_toggle.active = BooleanProperty(True)
                row.add_widget(meta_toggle)
                row.add_widget(Label(text=meta_toggle.meta_option))
                meta_widgets.append(meta_toggle)
                similar[meta_option].append(meta_toggle)

            rows.add_widget(row)
        self.add_widget(rows)

        for w in meta_widgets:
            try:
               w.similar = similar[w.meta_option]
            except Exception as ex:
                pass

        self.meta_widgets = meta_widgets

    def set_layout_region(self, region_area, region_name):
        self.cell_spec.cell_layout_map[region_area] = region_name
        self.generate_preview()

    def set_margin(self, margin_name, margin_amout, widget=None):
        try:
            self.cell_spec.cell_layout_margins[margin_name] = int(margin_amout)
        except Exception as ex:
            if widget:
                widget.text = ""
        self.generate_preview()

    def generate_preview(self):
        preview = cell_preview(self.cell_spec, cells=3)[1]
        self.cells_preview.texture = CoreImage(preview, ext="jpg", keep_data=True).texture
        try:
            self.parent.generate_structure()
        except AttributeError:
            pass

class CellSpecGenerator(BoxLayout):
    def __init__(self, cell_spec_container, palette_source=None, amount_source=None, **kwargs):
        self.cell_spec_container = cell_spec_container
        self.palette_source = palette_source
        self.amount_source = amount_source

        super(CellSpecGenerator, self).__init__(**kwargs)
        create_button = Button(text="create spec", size_hint_y=None, height=44)
        create_button.bind(on_release=self.create_cell_spec)
        self.add_widget(create_button)

    def create_cell_spec(self, widget, cell_spec_args=None):
        if cell_spec_args is None:
            cell_spec_args = {}
        cell_spec = CellSpecItem(CellSpec(palette=self.palette_source, amount=self.amount_source, **cell_spec_args))
        self.cell_spec_container.add_cell_spec(cell_spec)

    def specs(self):
        s = []
        for spec in self.children:
            s.append(spec.cell_spec)
        return s

class SourcesPreview(BoxLayout):
    def __init__(self, app=None, **kwargs):
        self.parameters = {}
        self.prefix = "glworb:*"
        self.sources_unfiltered = TextInput(multiline=True)
        self.sources = []
        self.source_fields = set()
        self.source_field_possibilities = {}
        self.samples_per_key = 5
        self.app = app
        self.samplings = 3
        self.remaining_samplings = self.samplings
        super(SourcesPreview, self).__init__(**kwargs)
        self.viewerclasses = [ c for c in inspect.getmembers(sys.modules[__name__], inspect.isclass) if "ViewViewer" in c[0]]
        self.item_preview = BoxLayout(orientation="vertical")
        self.scheduled_poll = None
        preview = BoxLayout()
        bottom = BoxLayout(size_hint_y=1, orientation="vertical")
        db_input = BoxLayout(size_hint_y=.3, size_hint_x=1, orientation="vertical")
        bottom_input = BoxLayout(size_hint_y=None, height=30)
        parameter_widget = TextInput(multiline=False, hint_text=self.prefix)
        parameter_widget.bind(on_text_validate=lambda widget: [setattr(self, 'prefix', widget.text), self.get_sources()])
        sample_widget = TextInput(multiline=False, hint_text=str(self.samples_per_key))
        sample_widget.bind(on_text_validate=lambda widget: [setattr(self, 'samples_per_key', int(widget.text)), self.sample_sources()])
        host = redis_conn.connection_pool.connection_kwargs["host"]
        port = redis_conn.connection_pool.connection_kwargs["port"]
        self.host_widget = TextInput(multiline=False, hint_text=str(host))
        self.port_widget = TextInput(multiline=False, hint_text=str(port))
        self.port_widget.bind(on_text_validate=lambda widget: self.change_db_settings())
        self.host_widget.bind(on_text_validate=lambda widget: self.change_db_settings())
        self.poll_widget = CheckBox()
        self.keyspace_widget = CheckBox()
        self.keyspace_widget.active = BooleanProperty(True)
        self.poll_widget.bind(active=lambda widget, value: self.change_db_settings(widget))
        self.keyspace_widget.bind(active=lambda widget, value: self.change_db_settings(widget))
        self.poll_input = TextInput(multiline=False, text=str(10))
        self.lookup_button = Button(text="lookup")
        self.lookup_button.bind(on_press=lambda widget: self.change_db_settings(widget))

        for row in ((Label(text="host"), self.host_widget),
                    (Label(text="port"), self.port_widget),
                    (self.lookup_button,),
                    (self.poll_widget, Label(text="poll (seconds)"), self.poll_input),
                    (self.keyspace_widget, Label(text="keyspace")),
                    (Label(text="prefix"), parameter_widget)
                    ):
            row_container = BoxLayout(size_hint_y=1, size_hint_x=1, height=30)
            for item in row:
                row_container.add_widget(item)
            db_input.add_widget(row_container)


        bottom_input.add_widget(Label(text="samples"))
        bottom_input.add_widget(sample_widget)
        bottom.add_widget(db_input)
        bottom.add_widget(bottom_input)
        sources_overview = BoxLayout(orientation="vertical", size_hint_y=None, height=1000, minimum_height=200)
        sources_scroll = ScrollView(bar_width=20)
        sources_scroll.add_widget(sources_overview)
        bottom.add_widget(sources_scroll)
        self.sources_overview = sources_overview

        self.key_selection = DropDownInput()
        self.load_key_as = DropDownInput(preload=[c[0] for c in self.viewerclasses])
        self.annotation = DropDownInput(preload=["META_FILENAME"])

        input_bar = BoxLayout(size_hint_y=None, height=30)
        self.key_selection.bind(on_text_validate=lambda widget: self.generate_preview())
        self.load_key_as.bind(on_text_validate=lambda widget: self.generate_preview())
        self.annotation.bind(on_text_validate=lambda widget: self.generate_preview())

        input_bar.add_widget(self.key_selection)
        input_bar.add_widget(self.load_key_as)
        input_bar.add_widget(self.annotation)
        preview.add_widget(self.item_preview)
        preview.add_widget(input_bar)
        self.add_widget(preview)
        self.add_widget(bottom)
        self.get_sources()

    def change_db_settings(self, widget=None):
        global r_ip
        global r_port
        global binary_r
        global redis_conn
        if widget == self.lookup_button:
            r_ip, r_port = data_models.service_connection()
            binary_r = redis.StrictRedis(host=r_ip, port=r_port)
            redis_conn = redis.StrictRedis(host=r_ip, port=r_port, decode_responses=True)
            self.host_widget.text = r_ip
            self.port_widget.text = str(r_port)
        elif self.host_widget.text and self.port_widget.text:
            db_settings = {"host" : self.host_widget.text, "port" : int(self.port_widget.text)}
            binary_r = redis.StrictRedis(**db_settings)
            redis_conn = redis.StrictRedis(**db_settings, decode_responses=True)

        if self.keyspace_widget.active and widget == self.keyspace_widget:
            self.app.db_event_subscription = redis_conn.pubsub()
            self.app.db_event_subscription.psubscribe(**{'__keyspace@0__:*': self.app.handle_db_events})
            self.app.db_event_subscription.thread = self.app.db_event_subscription.run_in_thread(sleep_time=0.001)
        elif not self.keyspace_widget.active and widget == self.keyspace_widget:
            self.app.db_event_subscription.thread.stop()

        if self.poll_widget.active and widget == self.poll_widget:
            try:
                self.scheduled_poll.cancel()
            except AttributeError:
                pass
            self.scheduled_poll = Clock.schedule_interval(lambda foo: self.get_sources(), int(self.poll_input.text))
        elif not self.poll_widget.active and widget == self.poll_widget:
            self.scheduled_poll.cancel()

        # clear source fields, if any from previous db
        self.source_fields = set()
        self.remaining_samplings = self.samplings
        self.get_sources()

    def generate_preview(self):
        try:
            self.item_preview.clear_widgets()
            self.item_preview.add_widget(Label(text="{}({})".format(self.key_selection.text, self.load_key_as.text)))
            self.item_preview.add_widget(Label(text="{}".format(self.annotation.text)))
            self.item_class = [c[1] for c in self.viewerclasses if c[0] == self.load_key_as.text][0]
            self.item_key = self.key_selection.text
            self.app.session["folds"].create_folds()
        except IndexError:
            # no viewerclass selected
            pass

    def init(self):
        self.key_selection.preload = sorted(list(self.source_fields))
        self.annotation.preload.extend(sorted(list(self.source_fields)))

    def get_sources(self):
        print("getting sources")
        self.source_keys = list(redis_conn.scan_iter(match=self.prefix))
        self.sources = []
        for key in self.source_keys:
            self.sources.append(redis_conn.hgetall(key))

        self.preprocess_sources()
        self.sources_unfiltered.text = "\n".join(self.source_keys)
        if self.remaining_samplings > 0:
            self.sample_sources()
        try:
            self.app.session["folds"].create_folds()
        except KeyError:
            pass

    def preprocess_sources(self):
        # all values come from redis as strings
        # try to convert values to int
        # add as checkbox/dropdown somewhere?
        for source in self.sources:
            for k, v in source.items():
                try:
                    source[k] = int(v)
                except:
                    pass

    def sample_sources(self):
        sampled_overview = {}
        self.sources_overview.clear_widgets()
        self.sources_overview.height = 0
        for source in self.sources:
            self.source_fields.update(list(source.keys()))
        self.key_selection.preload = sorted(list(self.source_fields))
        # try to update dropdowns
        try:
            self.app.session["palette"].update_names()
        except KeyError:
            pass

        for source in self.sources:
            for k, v in source.items():
                if not k in self.source_field_possibilities:
                    self.source_field_possibilities[k] = set()
                self.source_field_possibilities[k].add(v)

        for key in self.source_fields:
            sampled_overview[key] = []
            for _ in range(self.samples_per_key):
                try:
                    sampled_overview[key].append(random.choice(self.sources)[key])
                except KeyError:
                    pass
                except IndexError:
                    pass

        column_names = BoxLayout(orientation="horizontal")
        column_names.add_widget(Label(text=" "*10))
        for viewer_class in self.viewerclasses:
            column_names.add_widget(Label(text=viewer_class[0]))
        self.sources_overview.add_widget(column_names)

        for sample_key, samples in sampled_overview.items():
            self.sources_overview.add_widget(Label(text=str(sample_key)))
            for sample in samples:
                sample_row = BoxLayout(orientation="horizontal", size_hint_y=1)
                sample_row.add_widget(Label(text=str(repr(sample))))
                for viewer_class in self.viewerclasses:
                    try:
                        a = viewer_class[1](sample)
                        sample_row.add_widget(a)
                    except:
                        sample_row.add_widget(Label(text="X"))
                self.sources_overview.add_widget(sample_row)
                self.sources_overview.height += sample_row.height

        if self.remaining_samplings > 0:
            self.remaining_samplings -= 1

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

class AnnotatedImageViewViewer(BoxLayout):
    def __init__(self, source, **kwargs):
        self.source = source
        super(AnnotatedImageViewViewer, self).__init__(**kwargs)
        try:
            resize_to = 600
            image_data = bimg_resized(source, resize_to)
            img = ClickableImage(size_hint_y=None,
                                 size_hint_x=None,
                                 allow_stretch=True,
                                 keep_ratio=True)
            img.texture = CoreImage(image_data, ext="jpg").texture
            self.add_widget(img)
            self.add_widget(Label(text="----"))
            self.size = img.norm_image_size
        except Exception as ex:
            print(ex)
            raise ValueError("")

class ImageViewViewer(ClickableImage):
    def __init__(self, source, **kwargs):
        self.source = source
        # self.size_hint_y=None
        # self.size_hint_x=None
        # self.allow_stretch=True
        # self.keep_ratio=True
        try:
            resize_to = 600
            image_data = bimg_resized(source, resize_to)
            self.texture = CoreImage(image_data, ext="jpg").texture
            self.size = self.norm_image_size
        except Exception as ex:
            print(ex)
            raise ValueError("")
        super(ImageViewViewer, self).__init__(**kwargs)

class TextViewViewer(BoxLayout):
    def __init__(self, source, **kwargs):
        self.source = source
        super(TextViewViewer, self).__init__(**kwargs)
        self.add_widget(Label(text=str(source)))

class BindingItem(BoxLayout):
    def __init__(self, domain, action, action_keybindings, actions, **kwargs):
        # self.rows = 1
        # self.cols = None
        self.orientation = "horizontal"
        self.keys = action_keybindings[0]
        self.modifiers = action_keybindings[1]
        self.domain = domain
        self.action = action
        self.actions = actions
        self.action_label = Label(text=str(self.action), height=40)
        self.keys_input = TextInput(text=str(",".join(self.keys)), multiline=False, height=40, size_hint_x=0.2)
        self.keys_input.bind(on_text_validate = lambda widget: self.set_binding())
        self.modifiers_input = TextInput(text=str(",".join(self.modifiers)), multiline=False, height=40, size_hint_x=0.2)
        self.modifiers_input.bind(on_text_validate = lambda widget: self.set_binding())
        super(BindingItem, self).__init__()
        self.add_widget(self.action_label)
        self.add_widget(self.keys_input)
        self.add_widget(self.modifiers_input)

    def set_binding(self):
        self.keys = self.parse_input(self.keys_input.text)
        self.modifiers= self.parse_input(self.modifiers_input.text)
        self.actions[self.domain][self.action] = [self.keys, self.modifiers]

    def parse_input(self, text):
        text = text.strip()
        text = text.replace(" ", "")
        return text.split(",")

class StructurePreview(BoxLayout):
    def __init__(self, spec_source=None, palette_source=None, source_source=None, app=None, **kwargs):
        self.orientation = "vertical"
        self.preview_image = Image()
        self.spec_source = spec_source
        self.palette_source = palette_source
        self.source_source = source_source
        self.app = app
        self.parameters = {}
        self.parameters["additional_test"] = 0
        self.parameters["cell_width"] = 40
        self.parameters["cell_height"] = 40
        self.parameters["column_slots"] = 5
        self.checkbox_widgets = []
        self.parameter_widgets = []
        super(StructurePreview, self).__init__(**kwargs)
        top = BoxLayout(size_hint_y=1)
        bottom = BoxLayout(size_hint_y=None, height=30)
        top.add_widget(self.preview_image)
        self.add_widget(top)

        for parameter in ["cell_width", "cell_height", "column_slots", "additional_test"]:
            bottom.add_widget(Label(text=parameter))
            parameter_widget = DropDownInput()
            parameter_widget.bind(on_text_validate=lambda widget, parameter=parameter: self.set_parameter(parameter, widget.text))
            parameter_widget.parameter = parameter
            try:
                if self.parameters[parameter]:
                    parameter_widget.text = str(self.parameters[parameter])
            except KeyError:
                pass
            bottom.add_widget(parameter_widget)
            self.parameter_widgets.append(parameter_widget)

        for check_parameter in ["sources", "sparse_expected", "sparse_found", "sparse_found_from_zero", "ragged", "ragged_sub", "start_offset"]:
            check_parameter_widget = CheckBox()
            check_parameter_widget.text = check_parameter
            check_parameter_widget.bind(active=self.set_check_parameter)
            try:
                if self.parameters[check_parameter] == True:
                    check_parameter_widget.active = BooleanProperty(True)
            except Exception as ex:
                pass

            bottom.add_widget(check_parameter_widget)
            bottom.add_widget(Label(text=check_parameter))
            self.checkbox_widgets.append(check_parameter_widget)

        self.add_widget(bottom)
        self.generate_structure_preview(parameters=self.parameters)

    def update_parameter_widgets(self):
        for widget in self.checkbox_widgets:
            try:
                if self.parameters[widget.text] == True:
                    if not widget.active:
                        widget.active = BooleanProperty(True)
            except Exception as ex:
                pass

        for widget in self.parameter_widgets:
            try:
                widget.text = str(self.parameters[widget.parameter])
            except Exception as ex:
                pass

    def set_check_parameter(self, widget, value):
        # something is setting "sources" to a BooleanProperty
        # for now just filter out
        if not isinstance(value, BooleanProperty):
            self.parameters[widget.text] = value
            self.generate_structure_preview(parameters=self.parameters)

    def set_parameter(self, parameter, value):
        try:
            self.parameters[parameter] = int(value)
        except:
            pass
        self.generate_structure_preview(parameters=self.parameters)

    def generate_structure_preview(self, parameters=None, create_folds=None):

        generate_call = lambda dt, self=self, parameters=parameters, create_folds=create_folds: self.generate_structure_preview_call(parameters=parameters, create_folds=create_folds)
        schedule = True
        for event in Clock.get_events():
            # check if lambda function is in events by matching repr strings
            if str(generate_call)[:40] in str(event.callback):
                schedule = False
        if schedule:
            print("structure scheduling generate call")
            Clock.schedule_once(generate_call, 1)
        else:
            print("structure generate call already scheduled")

    def generate_structure_preview_call(self, parameters=None, create_folds=None):
        print("generating...", parameters)
        if create_folds is None:
            create_folds = True
        self.update_parameter_widgets()
        if parameters is None:
            parameters = {}
        sources = []
        specs = self.spec_source()
        try:
            if self.parameters["sources"]:
                sources = self.source_source.sources
        except:
            pass

        if not sources:
            for palette in self.palette_source():
                for thing in palette.possibilities:
                    for num in range(thing.rough_amount + self.parameters["additional_test"]):
                        sources.append({palette.name : thing.name, "meta_number" : num, "meta_random" : random.randint(0,1000), "meta_choice" : random.choice(["1","2"])})

        # lru cache may be useful here, but list is unhashable
        # and would have to be changed
        preview = structure_preview(sources, self.spec_source(), self.palette_source(), **parameters)[1]
        self.preview_image.texture = CoreImage(preview, ext="jpg", keep_data=True).texture
        if create_folds is True:
            self.app.session["folds"].create_folds()

    def generate_structure_columns(self, parameters=None):
        self.update_parameter_widgets()
        if parameters is None:
            parameters = {}
        sources = []
        specs = self.spec_source()
        try:
            if self.parameters["sources"]:
                sources = self.source_source.sources
        except:
            pass

        return structure_preview(sources, self.spec_source(), self.palette_source(), return_columns=True, **parameters)

class PaletteThingGenerator(BoxLayout):
    def __init__(self, palette_thing_container, **kwargs):
        self.palette_thing_container = palette_thing_container
        super(PaletteThingGenerator, self).__init__(**kwargs)
        create_button = Button(text="create palette thing", size_hint_y=None, height=44)
        create_button.bind(on_release=self.create_palette_thing)
        self.add_widget(create_button)

    def create_palette_thing(self, widget, palette_args=None):
        if palette_args is None:
            palette_args = {}
        palette_thing = PaletteThingItem(PaletteThing(**palette_args))
        self.palette_thing_container.add_palette_thing(palette_thing)

class PaletteThingContainer(BoxLayout):
    def __init__(self, **kwargs):
        self.app = None
        super(PaletteThingContainer, self).__init__(**kwargs)

    def palette(self):
        p = []

        for palette_thing in self.children:
            p.append(palette_thing.palette_thing)
        return p

    def add_palette_thing(self, palette_thing):
        palette_thing.height = 44
        palette_thing.size_hint_y = None
        self.add_widget(palette_thing)
        self.parent.scroll_to(palette_thing)

    def remove_palette_thing(self, palette_thing_id):
        for palette_thing in self.children:
            try:
                if palette_thing == palette_thing_id:
                    del palette_thing.palette_thing
                    self.remove_widget(palette_thing)
            except AttributeError as ex:
                pass

    def update_names(self):
        for palette_thing in self.children:
            try:
                palette_thing.set_palette_thing_name.preload = list(self.app.session["sources"].source_fields)
                # try to add possibilities
                if palette_thing.autogen_possibilities is True:
                    try:
                        for possibility in sorted(self.app.session["sources"].source_field_possibilities[palette_thing.palette_thing.name]):
                            if not possibility in [colormap.name for colormap in palette_thing.possibilities]:
                                palette_thing.add_possibility(possibility)
                    except KeyError:
                        pass
            except AttributeError as ex:
                pass

class PaletteThingItem(BoxLayout):
    def __init__(self, palette_thing, **kwargs):
        self.palette_thing = palette_thing
        self.height = 60
        self.minimum_height = 60
        self.size_hint_y = None
        self.autogen_possibilities = False
        super(PaletteThingItem, self).__init__(**kwargs)
        self.generate_palette_overview()

    def generate_palette_overview(self):
        self.clear_widgets()
        container = BoxLayout(orientation="vertical", size_hint_y=None)
        row  = BoxLayout(orientation="horizontal", size_hint_y=1)
        row_bottom  = BoxLayout(orientation="horizontal", size_hint_y=1)
        autogen_checkbox = CheckBox()
        autogen_checkbox.bind(active=lambda widget, value: [setattr(self, "autogen_possibilities", widget.active), self.parent.update_names()])
        row.add_widget(Label(text=""))
        row.add_widget(autogen_checkbox)
        row.add_widget(Label(text="autogen"))
        ordering = DropDownInput(hint_text=str(self.palette_thing.order_value))
        row.add_widget(ordering)
        ordering.bind(on_text_validate=lambda widget: self.set_order(widget.text, widget))

        color_button = Button(text="", background_normal='')
        color_button.bind(on_press= lambda widget=self, thing=self.palette_thing: self.pick_color(widget, thing))
        color_button.background_color = (*self.palette_thing.color.rgb, 1)
        row.add_widget(color_button)

        set_palette_thing_name = DropDownInput(text=self.palette_thing.name)
        set_palette_thing_name.bind(on_text_validate=lambda widget: self.set_name(widget.text))
        self.set_palette_thing_name = set_palette_thing_name
        row.add_widget(set_palette_thing_name)
        add_possibility = DropDownInput()
        add_possibility.bind(on_text_validate=lambda widget: self.add_possibility(widget.text))
        row.add_widget(add_possibility)

        for color_map_thing in sorted(self.palette_thing.possibilities, key=lambda cm: cm.order_value, reverse=True):
            color_map_container = BoxLayout(orientation="vertical")
            color_map_row_top = BoxLayout()
            color_map_row_bottom = BoxLayout()

            possibility_color = color_map_thing.color.rgb
            color_button = Button(text= color_map_thing.name, background_normal='')
            color_button.possibility_name = color_map_thing.name
            color_button.bind(on_press= lambda widget=self, thing=color_map_thing: self.pick_color(widget, thing))
            color_button.background_color = (*possibility_color, 1)
            color_map_row_top.add_widget(color_button)
            rough_amount = DropDownInput(hint_text=str(color_map_thing.rough_amount))
            rough_amount.bind(on_text_validate= lambda widget, thing=color_map_thing: self.set_rough_amount(widget.text, thing))
            possibility_ordering = DropDownInput(hint_text=str(color_map_thing.order_value))
            possibility_ordering.bind(on_text_validate=lambda widget, thing=color_map_thing: self.set_possibility_order(widget.text, thing))
            possibility_delete = Button(text="del")
            possibility_delete.bind(on_press=lambda widget, color_map_thing=color_map_thing: self.remove_possibility(color_map_thing))
            color_map_row_bottom.add_widget(possibility_ordering)
            color_map_row_bottom.add_widget(rough_amount)
            color_map_row_bottom.add_widget(possibility_delete)
            color_map_container.add_widget(color_map_row_top)
            color_map_container.add_widget(color_map_row_bottom)
            row.add_widget(color_map_container)

        container.add_widget(row)
        container.add_widget(row_bottom)
        self.add_widget(container)

    def set_possibility_order(self, order, possibility):
        try:
            possibility.order_value = float(order)
            self.generate_palette_overview()
            self.broadcast_update()
        except:
            pass

    def set_order(self, order, widget=None):
        try:
            self.palette_thing.order_value = float(order)
            self.broadcast_update()
        except:
            pass

    def set_rough_amount(self, amount, thing):
        try:
            thing.rough_amount = int(amount)
            self.generate_palette_overview()
            self.broadcast_update()
        except ValueError as ex:
            pass

    def set_name(self, name):
        self.palette_thing.name = name
        self.generate_palette_overview()
        self.broadcast_update()

    def remove_possibility(self, color_map):
        self.palette_thing.possibilities.remove(color_map)
        self.generate_palette_overview()
        self.broadcast_update()

    def add_possibility(self, name):
        thing = ColorMapThing(name=name)
        self.palette_thing.possibilities.append(thing)
        self.generate_palette_overview()
        self.broadcast_update()

    def pick_color(self, set_widget=None, set_thing=None, *args):
        color_picker = ColorPickerPopup()
        color_picker.content.bind(color = lambda widget, value, set_widget=set_widget, set_thing=set_thing: self.on_color(widget, value, set_widget, set_thing))
        color_picker.open()

    def on_color(self, instance, value, target_widget, thing, *args):
        thing.color = colour.Color(rgb=instance.color[:3])
        target_widget.background_color = (*thing.color.rgb, 1)
        self.generate_palette_overview()
        self.broadcast_update()

    def broadcast_update(self):
        self.parent.app.session['cellspec'].generate_previews()

class AccordionItemThing(AccordionItem):
    def __init__(self, **kwargs):
        super(AccordionItemThing, self).__init__(**kwargs)
        self.thing = None

    def render_contents(self):
        # sources may have changed, remove widgets if widget.source is no longer in sources
        # remember that self.sources may contain spaceholding Nones
        for item in self.thing.image_grid.children:
            try:
                if not item.source in [source[self.parent.app.session['sources'].item_key] for source in self.sources if source and self.parent.app.session['sources'].item_key in source]:
                    self.thing.image_grid.remove_widget(item)
            except Exception as ex:
                pass

        for source_index, source in enumerate(reversed(self.sources)):
            try:
                if source is not None:
                    if not source[self.parent.app.session['sources'].item_key] in [s.source for s in self.thing.image_grid.children]:
                        try:
                            item = self.parent.app.session['sources'].item_class(source[self.parent.app.session['sources'].item_key], size_hint_y=None, size_hint_x=None)
                            # add widget in correct position using index parameter
                            self.thing.image_grid.add_widget(item, index=source_index)
                        except Exception as ex:
                            pass
            except Exception as ex:
                pass

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos):
            if self.collapse is False:
                self.parent.open_column_position = self.column_index
                self.render_contents()
        return super(AccordionItemThing, self).on_touch_up(touch)

class AccordionContainer(Accordion):
    def __init__(self, **kwargs):
        self.resize_size = 600
        self.folded_fold_width = 40
        self.folded_fold_height = Window.size[1]
        self.open_column_position = 0
        super(AccordionContainer, self).__init__(anim_duration=0, min_space=self.folded_fold_width)

    def create_folds(self):
            folds_call = lambda dt, self=self: self.create_folds_call()
            schedule = True
            for event in Clock.get_events():
                # check if lambda function is in events by matching repr strings
                if str(folds_call)[:40] in str(event.callback):
                    schedule = False
            if schedule:
                print("scheduling create folds call")
                Clock.schedule_once(folds_call, 1)
            else:
                print("create folds call already scheduled")

    def create_folds_call(self):
        # this sets the fold width to match column images correctly
        # ie a square cell will be shown as square on accordion fold
        # however in situations with fewer cells per column, there
        # will be no overlap and opening a fold will have no effect
        # since there is no spare space to expand
        # try:
        #     self.min_space = self.app.session['structure'].parameters['cell_width']
        # except KeyError:
        #     pass
        try:
            # folds still use filenames from disk by
            # setting background_normal and background_selected
            # useful to set image directly using available filebytes
            # and not need to write images to disk
            column_number = 0
            try:
                filenames, filebytes, sources = zip(*self.app.session['structure'].generate_structure_columns(parameters=self.app.session['structure'].parameters))
                # remove or add folds to match filenames/sources
                if len(self.children) > len(sources):
                    for child in self.children[len(self.children) - len(sources):]:
                        self.remove_widget(child)
                elif len(self.children) < len(sources):
                    for _ in range(len(sources) - len(self.children)):
                        fold = AccordionItemThing()
                        fold.thing = ScatterTextWidget()
                        fold.add_widget(fold.thing)
                        self.add_widget(fold)

                for fold, filename, source in zip(reversed(self.children), filenames, sources):
                    fold.sources = source
                    fold.column_index = column_number
                    fold.background_normal = filename
                    fold.background_selected = filename
                    if fold.collapse is False:
                        fold.render_contents()
                    column_number += 1
            except ValueError:
                # no columns
                self.clear_widgets()

        except KeyError:
            pass
        try:
            generate_call = lambda dt, self=self: self.app.session['structure'].generate_structure_preview(parameters=self.app.session['structure'].parameters, create_folds=False)

            schedule = True
            for event in Clock.get_events():
                # check if lambda function is in events by matching repr strings
                # will be something like <function StructurePreview.generate_structure_preview...
                if str(generate_call)[:40] in str(event.callback):
                    schedule = False
            if schedule:
                print("scheduling folds generate call")
                Clock.schedule_once(generate_call, 1)
            else:
                print("folds generate call already scheduled")
            # if not str(generate_call)[:40] in [str(event.callback) for event in Clock.get_events()]:
            #     print("scheduling folds call.........................", generate_call)
            #     Clock.schedule_once(generate_call, 10)
            # else:
            #     print("folds generate call already scheduled")

            #self.app.session['structure'].generate_structure_preview(parameters=self.app.session['structure'].parameters, create_folds=False)
        except KeyError:
            pass

        # check if folds need to be resized
        # more folds will need narrower min_space
        try:
            fold_width = int(Window.size[0] / len(self.children))
            #accordion does not like exact value of children width and total width
            if fold_width * len(self.children) == Window.size[0]:
                fold_width -= 1
            if fold_width < self.min_space:
                print(fold_width,  len(self.children), Window.size[0])
                self.min_space = fold_width
                self.folded_fold_width = fold_width
                print("resizing folds to {}".format(self.folded_fold_width))
        except ZeroDivisionError:
            pass

    def contents_view_down(self):
        for i, c in enumerate(self.children):
            try:
                c.thing.scroller.scroll_y -= (1/c.thing.image_grid.rows)
            except TypeError:
                pass

    def contents_view_up(self):
        for i, c in enumerate(self.children):
            try:
                c.thing.scroller.scroll_y += (1/c.thing.image_grid.rows)
            except TypeError:
                pass

    def contents_view_left(self):
        for i, c in enumerate(self.children):
            try:
                c.thing.scroller.scroll_x -= (1/len(c.thing.image_grid.children))
            except TypeError:
                # print(c.thing.image_grid.cols)
                pass

    def contents_view_right(self):
        for i, c in enumerate(self.children):
            try:
                c.thing.scroller.scroll_x += (1/len(c.thing.image_grid.children))
            except TypeError:
                # print(c.thing.image_grid.cols)
                pass

    def contents_grow_columns(self):
        for i, c in enumerate(self.children):
            if c.thing.image_grid.rows is None:
                if c.thing.image_grid.cols - 1 > 0:
                    c.thing.image_grid.cols -= 1
            elif c.thing.image_grid.cols is None:
                if c.thing.image_grid.rows - 1 > 0:
                    c.thing.image_grid.rows -= 1

    def contents_shrink_columns(self):
        for i, c in enumerate(self.children):
            if c.thing.image_grid.rows is None:
                c.thing.image_grid.cols += 1
            elif c.thing.image_grid.cols is None:
                c.thing.image_grid.rows += 1

    def fold_shrink_width(self):
        if self.folded_fold_width - 5 > 0:
            self.folded_fold_width -= 5
            print(self.folded_fold_width)
        self.min_space = self.folded_fold_width

    def fold_grow_width(self):
        self.folded_fold_width += 5
        print(self.folded_fold_width)
        self.min_space = self.folded_fold_width

    def fold_unfold_next(self):
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

    def fold_unfold_previous(self):
        for i, c in enumerate(self.children):
            if c.collapse is False:
                self.children[i-1].collapse = False
                c.collapse = True
                break

    def contents_enlarge(self):
        for i, c in enumerate(self.children):
            if c.collapse is False:
                c.thing.scroller.enlarge()
                break

    def contents_shrink(self):
        for i, c in enumerate(self.children):
            if c.collapse is False:
                c.thing.scroller.shrink()
                break

    def contents_enlarge_all(self):
        for i, c in enumerate(self.children):
            c.thing.scroller.enlarge()

    def contents_shrink_all(self):
        for i, c in enumerate(self.children):
            c.thing.scroller.shrink()

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

def bimg_resized(uuid, new_size, linking_uuid=None):
    contents = binary_r.get(uuid)
    f = io.BytesIO()
    f = io.BytesIO(contents)
    img = PImage.open(f)
    img.thumbnail((new_size, new_size), PImage.ANTIALIAS)
    extension = img.format
    # if linking_uuid:
    #     data_model_string = data_models.pretty_format(redis_conn.hgetall(linking_uuid), linking_uuid)
    #     # escape braces
    #     data_model_string = data_model_string.replace("{","{{")
    #     data_model_string = data_model_string.replace("}","}}")
    #     img = data_models.img_overlay(img, data_model_string, 50, 50, 12)
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
        # handle keybindings
        self._keyboard = Window.request_keyboard(self._keyboard_closed, self)
        self._keyboard.bind(on_key_down=self._on_keyboard_down)
        self.actions = bindings.keybindings()
        self.session_save_path = "~/.config/fold/"
        self.session_save_filename = "session.xml"
        self.session = {}
        self.restore_session = True
        self.xml_files_to_load = []
        if kwargs["db_host"] and kwargs["db_port"]:
            global binary_r
            global redis_conn
            db_settings = {"host" :  kwargs["db_host"], "port" : kwargs["db_port"]}
            binary_r = redis.StrictRedis(**db_settings)
            redis_conn = redis.StrictRedis(**db_settings, decode_responses=True)


        super(FoldedInlayApp, self).__init__()

    def on_stop(self):
        # stop pubsub thread if window closed with '[x]'
        self.db_event_subscription.thread.stop()

    def app_exit(self):
        self.db_event_subscription.thread.stop()
        App.get_running_app().stop()

    def handle_db_events(self, message):
        # print(message)
        #if self.session['sources'].prefix.replace("*","") in message["channel"]:
        if fnmatch.fnmatch(message["channel"].replace("__keyspace@0__:",""), self.session['sources'].prefix):
            get_sources = lambda dt:  self.session['sources'].get_sources()
            schedule = True
            for event in Clock.get_events():
                # check if lambda function is in events by matching repr strings
                if str(get_sources)[:40] in str(event.callback):
                    schedule = False
            if schedule:
                print("scheduling get sources call")
                Clock.schedule_once(get_sources, 1)
            else:
                print("get sources call already scheduled")

    def _keyboard_closed(self):
        # do not unbind the keyboard because
        # if keyboard is requested by textinput
        # widget, this keyboard used for app keybinds
        # will be unbound and not rebound after
        # defocusing textinput widget
        #
        # self._keyboard.unbind(on_key_down=self._on_keyboard_down)
        # self._keyboard = None
        pass

    def _on_keyboard_down(self, keyboard, keycode, text, modifiers):
        for actions in ["app", self.root.current_tab.text]:
            try:
                for k, v in self.actions[actions].items():
                    if keycode[1] in v[0] and not v[1] and not modifiers:
                        try:
                            getattr(self, "{}".format(k))()
                        except Exception as ex:
                            pass

                        try:
                            getattr(self.root.current_tab.content, "{}".format(k))()
                        except Exception as ex:
                            pass

                        # use .content.children for tabs
                        for c in self.root.current_tab.content.children:
                            try:
                                getattr(c, "{}".format(k))()
                            except Exception as ex:
                                pass

                        # for lower_widget in self.root.current_tab.sub_content:
                        #     for c in lower_widget.children:
                        #         try:
                        #             getattr(c, "{}".format(k))()
                        #         except Exception as ex:
                        #             print(ex)

                    elif keycode[1] in v[0] and modifiers:
                        if len(set(v[1]).intersection(set(modifiers))) == len(modifiers):
                            try:
                                getattr(self, "{}".format(k))()
                            except Exception as ex:
                                pass

                        try:
                            getattr(self.root.current_tab.content, "{}".format(k))()
                        except Exception as ex:
                            pass

                            for c in self.root.current_tab.content.children:
                                try:
                                    getattr(c, "{}".format(k))()
                                except Exception as ex:
                                    pass

                            # for lower_widget in self.root.current_tab.sub_content:
                            #     for c in lower_widget.children:
                            #         try:
                            #             getattr(c, "{}".format(k))()
                            #         except Exception as ex:
                            #             print(ex)
            except KeyError:
                pass

    def build(self):

        root =  TabbedPanel(do_default_tab=False)
        self.root = root
        folds = AccordionContainer(orientation='horizontal', **self.kwargs)
        folds.app = self
        config = BoxLayout(orientation="vertical")
        preview = BoxLayout(orientation="vertical")
        sources = BoxLayout(orientation="vertical")

        top = BoxLayout()
        bottom = BoxLayout(size_hint_y=None)
        palette_layout = PaletteThingContainer(orientation="vertical", size_hint_y=None, height=800, minimum_height=200)
        palette_layout.app = self
        palette_scroll = ScrollView(bar_width=20)
        palette_scroll.add_widget(palette_layout)

        cellspec_layout = CellSpecContainer(orientation="vertical", size_hint_y=None, height=800, minimum_height=200)
        cellspec_layout.app = self
        cellspec_scroll = ScrollView(bar_width=20)
        cellspec_scroll.add_widget(cellspec_layout)

        # cellspec_layout.add_widget(CellSpecItem(CellSpec("foo", palette=palette_layout.palette, amount=palette_layout.amount)))
        # palette_layout.add_widget(PaletteThingItem(PaletteThing("foo")))
        top.add_widget(cellspec_scroll)
        top.add_widget(palette_scroll)
        cell_spec_generator = CellSpecGenerator(cellspec_layout, palette_source=palette_layout.palette)
        bottom.add_widget(cell_spec_generator)
        bottom.add_widget(PaletteThingGenerator(palette_layout))

        config.add_widget(top)
        config.add_widget(bottom)

        sources_preview = SourcesPreview(app=self)
        sources.add_widget(sources_preview)
        self.session['folds'] = folds

        # for now
        # create bindings_container as boxlayout
        # instead of class BindingsContainer(BoxLayout)
        # since settings do not seem to be correctly set
        # in order to work with scrollview
        bindings_container = BoxLayout(orientation="vertical",
                                       size_hint_y=None,
                                       )

        actions = 0
        for domain, domain_actions in self.actions.items():
            bindings_container.add_widget(Label(text=str(domain), height=40))
            for action, action_bindings in domain_actions.items():
                binding_widget = BindingItem(domain, action, action_bindings, self.actions, height=40)
                bindings_container.add_widget(binding_widget)
                actions += 1
        # set height for scrollview
        bindings_container.height = actions * 40
        bindings_scroll = ScrollView(bar_width=20)
        bindings_scroll.add_widget(bindings_container)

        structure_preview = StructurePreview(spec_source=cellspec_layout.spec, palette_source=palette_layout.palette, source_source=sources_preview, app=self)
        preview.add_widget(structure_preview)
        for top_level_item, title in [(config,"spec/palette"), (preview,"preview"), (folds,"folds"), (sources,"sources"), (bindings_scroll, "bindings")]:
            item = TabbedPanelItem(text="{}".format(title))
            item.add_widget(top_level_item)
            root.add_widget(item)

        # use session dict for saving / reloading session to/from xml
        self.session['palette'] = palette_layout
        self.session['cellspec'] = cellspec_layout
        self.session['cell_spec_generator'] = cell_spec_generator
        self.session['structure'] = structure_preview
        self.session['sources'] = sources_preview

        folds.structure = structure_preview
        sources_preview.init()
        self.load_session()

        self.db_event_subscription = redis_conn.pubsub()
        self.db_event_subscription.psubscribe(**{'__keyspace@0__:*': self.handle_db_events})
        # add thread to pubsub object to stop() on exit
        self.db_event_subscription.thread = self.db_event_subscription.run_in_thread(sleep_time=0.001)

        folds.create_folds()
        return root

    def generate_xml(self, write_output=False, output_filename=None, output_type=None, output_path=None):
        machine = etree.Element("machine")
        session = etree.Element("session")
        machine.append(session)

        #possibilities=[ColorMapThing(color=<Color #066e1f>, name='12', rough_amount=12)]
        for palette_thing in self.session['palette'].palette():
            palette = etree.Element("palette")
            palette.set("name", str(palette_thing.name))
            palette.set("color", str(palette_thing.color.hex_l))
            palette.set("order_value", str(palette_thing.order_value))
            for possibility in palette_thing.possibilities:
                p = etree.Element("possibility")
                p.set("color", str(possibility.color.hex_l))
                p.set("name", str(possibility.name))
                p.set("rough_amount", str(possibility.rough_amount))
                palette.append(p)
            session.append(palette)

        for cell_spec in self.session['cellspec'].spec():
            cellspec =  etree.Element("cellspec")
            cellspec.set("spec_for", cell_spec.spec_for)
            cellspec.set("primary_layout_field", cell_spec.primary_layout_field)
            layout_map =  etree.Element("map", name="layout_map")
            for k, v in cell_spec.cell_layout_map.items():
                layout_map.append(etree.Element("element", name=str(k), value=str(v)))

            layout_margins =  etree.Element("map", name="layout_margins")
            for k, v in cell_spec.cell_layout_margins.items():
                layout_margins.append(etree.Element("element", name=str(k), value=str(v)))

            layout_meta =  etree.Element("map", name="layout_meta")
            for k, v in cell_spec.cell_layout_meta.items():
                try:
                    element = etree.Element("element", name=k)
                    for value in v:
                        nested_value =  etree.Element("item", area=value[0], name=value[1])
                        element.append(nested_value)
                    layout_meta.append(element)
                except TypeError:
                    pass

            cellspec.append(layout_map)
            cellspec.append(layout_margins)
            cellspec.append(layout_meta)
            session.append(cellspec)

        structure =  etree.Element("structure")
        for parameter_name, parameter_value in self.session['structure'].parameters.items():
            structure.set(str(parameter_name), str(parameter_value))
        session.append(structure)

        if write_output is True:
            machine_root = etree.ElementTree(machine)
            xml_filename = output_filename
            if not os.path.isdir(output_path):
                os.mkdir(output_path)

            if os.path.isfile(os.path.join(output_path, output_filename)):
                os.remove(os.path.join(output_path, output_filename))

            if output_type == "xml":
                machine_root.write(os.path.join(output_path, xml_filename), pretty_print=True)

    def save_session(self):
        # self.save_defaults()
        # add hook to run on exit()
        expanded_path = os.path.expanduser(self.session_save_path)
        if not os.path.isdir(expanded_path):
            print("creating: {}".format(expanded_path))
            os.mkdir(expanded_path)
        self.generate_xml(write_output=True, output_filename=self.session_save_filename, output_path=expanded_path, output_type="xml")

    def load_session(self):
        # self.load_defaults()
        files_to_restore = []

        if self.restore_session is True:
            session_file = os.path.join(self.session_save_path, self.session_save_filename)
            session_file = os.path.expanduser(session_file)
            files_to_restore.append(session_file)

        for file in self.xml_files_to_load:
            files_to_restore.append(file)

        session_xml = {}
        project_xml = {}

        for file in files_to_restore:
            if os.path.isfile(file):
                try:
                    xml = etree.parse(file)
                    print("restoring {}".format(xml))
                    for session in xml.xpath('//session'):
                        # restore palettes
                        for palette in session.xpath('//palette'):
                            palette_args = {}
                            palette_args["name"] = str(palette.xpath("./@name")[0])
                            palette_args["color"] = colour.Color(str(palette.xpath("./@color")[0]))
                            palette_args["order_value"] = float(palette.xpath("./@order_value")[0])
                            palette_thing = PaletteThing(**palette_args)
                            for possibility in palette.xpath('.//possibility'):
                                possibility_args = {}
                                possibility_args["color"] = colour.Color(str(possibility.xpath("./@color")[0]))
                                possibility_args["name"] = str(possibility.xpath("./@name")[0])
                                possibility_args["rough_amount"] = int(float(possibility.xpath("./@rough_amount")[0]))
                                palette_thing.possibilities.append(ColorMapThing(**possibility_args))
                            palette_thing = PaletteThingItem(palette_thing)
                            self.session['palette'].add_palette_thing(palette_thing)

                        # restore cellspecs
                        for cellspec in session.xpath('//cellspec'):
                            cellspec_args = {}
                            cellspec_args["spec_for"] = str(cellspec.xpath("./@spec_for")[0])
                            cellspec_args["primary_layout_field"] = str(cellspec.xpath("./@primary_layout_field")[0])
                            for cellspecmap in cellspec.xpath('.//map'):
                                mapname = str(cellspecmap.xpath("./@name")[0])
                                cellspec_args["cell_"+mapname] = {}
                                name = None
                                value = None
                                for element in cellspecmap:# cellspecmap.xpath('.//element'): #cellspecmap: #cellspecmap.xpath('//element'):
                                    name = str(element.xpath("./@name")[0])
                                    try:
                                        value = str(element.xpath("./@value")[0])
                                        try:
                                            value = int(value)
                                        except:
                                            pass
                                        if value == "None":
                                            value = None
                                        cellspec_args["cell_"+mapname][name] = value
                                    except IndexError as ex:
                                        if not name in cellspec_args["cell_"+mapname]:
                                            cellspec_args["cell_"+mapname][name] = []
                                        if not cellspec_args["cell_"+mapname][name]:
                                            cellspec_args["cell_"+mapname][name] = []

                                        for item in element:
                                            item_name =  str(item.xpath("./@name")[0])
                                            item_area =  str(item.xpath("./@area")[0])
                                            if not (item_area, item_name) in cellspec_args["cell_"+mapname][name]:
                                                cellspec_args["cell_"+mapname][name].append((item_area, item_name))
                            # use generator
                            self.session['cell_spec_generator'].create_cell_spec(None, cell_spec_args=cellspec_args)

                        # restore structure parameters
                        for structure in session.xpath('//structure'):
                            for attrib in structure.attrib:
                                value = structure.get(attrib)
                                try:
                                    value = int(value)
                                except:
                                    pass
                                if value == "True":
                                    value = True
                                elif value == "False":
                                    value = False
                                self.session['structure'].parameters[attrib] = value
                            self.session['structure'].generate_structure_preview(parameters=self.session['structure'].parameters)
                except etree.XMLSyntaxError as ex:
                    print("cannot parse xml from file: {}, ignoring".format(file))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--xml-file",  help="xml file to use")
    parser.add_argument("--xml-key",  help="db key containing xml to access")
    parser.add_argument("--db-host",  help="db host ip, requires use of --db-port")
    parser.add_argument("--db-port", type=int, help="db port, requires use of --db-host")
    args = parser.parse_args()

    if bool(args.db_host) != bool(args.db_port):
        parser.error("--db-host and --db-port values are both required")

    app = FoldedInlayApp(**vars(args))
    atexit.register(app.save_session)
    app.run()