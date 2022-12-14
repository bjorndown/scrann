from typing import Union

import cairo
import gi

from scrann.log import log
from scrann.tools import Tool
from scrann.tools.crop import Crop
from scrann.tools.pen import Pen
from scrann.tools.rectangle import Rectangle

gi.require_version('Gtk', '3.0')
from gi.repository import GLib, Gtk, Gdk


class Main(Gtk.Window):
    _current_tool: Union[Tool, None]

    def __init__(self, filename):
        Gtk.Window.__init__(self, title='Scrann')
        self._color = (1, 0, 0, 1)
        self._filename = filename

        self.offset = [0, 0]

        self._setup_image_surface(filename)
        self._tools = [Pen(self._image_rect), Rectangle(self._image_rect), Crop(self._image_rect)]
        self._current_tool = None
        self._setup_event_box()
        self._setup_header_bar()

        self.set_border_width(10)
        self.set_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect('delete-event', Gtk.main_quit)
        self.show_all()
        GLib.timeout_add(50, self.redraw)

    def redraw(self):
        self._annotation_area.queue_draw()
        return True

    def _update_image_surface(self, surface: cairo.Surface):
        image_rect = cairo.Rectangle(0, 0, surface.get_width(), surface.get_height())
        self.set_default_size(image_rect.width, image_rect.height)

        self._image_context = cairo.Context(surface)
        self._image_context.set_source_rgba(0, 0, 0, 0)

    def _setup_image_surface(self, filename):
        image_surface = cairo.ImageSurface.create_from_png(filename)
        self._image_rect = cairo.Rectangle(0, 0, image_surface.get_width(), image_surface.get_height())
        self.set_default_size(self._image_rect.width, self._image_rect.height)

        self._image_context = cairo.Context(image_surface)
        self._image_context.set_source_rgba(0, 0, 0, 0)

        self._drawing_area = Gtk.DrawingArea()
        self._drawing_area.connect('draw', self.on_draw)

        self._annotation_area = Gtk.DrawingArea()
        self._annotation_area.connect('draw', self.on_draw_annotations)

    def on_draw_annotations(self, widget, cairo_context):
        for tool in self._tools:
            cairo_context.set_source_surface(tool.surface)
            cairo_context.paint()

    def on_draw(self, widget, cairo_context):
        cairo_context.set_source_surface(self._image_context.get_target(), *self.offset)
        cairo_context.paint()

    def _setup_header_bar(self):
        header_bar = Gtk.HeaderBar()
        header_bar.set_show_close_button(True)
        header_bar.props.title = self._filename
        self.set_titlebar(header_bar)
        self._setup_tools(header_bar)
        self._setup_color(header_bar)
        self._setup_undo(header_bar)
        self._setup_operations(header_bar)

    def _setup_tools(self, header_bar):
        self._tool_box = Gtk.ButtonBox(orientation=Gtk.Orientation.HORIZONTAL)

        def _create_tool_button(_tool):
            _button = Gtk.RadioButton.new_with_label(None, _tool.label)
            log.debug(f'connected {_tool.label}')
            _button.connect('toggled', self._change_tool(_tool))
            _button.set_mode(False)
            _button.set_active(False)
            self._tool_box.add(_button)
            return _button

        radio_group = _create_tool_button(self._tools[0])

        for tool in self._tools[1:]:
            button = _create_tool_button(tool)
            # button.join_group(radio_group)

        header_bar.pack_end(self._tool_box)

    def _change_tool(self, tool):
        def cb(widget):
            log.debug(f'using {tool.label}')
            self._current_tool = tool

        return cb

    def _setup_color(self, header_bar):
        button = Gtk.Button()
        drawing_area = Gtk.DrawingArea()
        drawing_area.connect('draw', self.on_color_picker_draw)
        button.add(drawing_area)

        color_pickerd = Gtk.ColorChooserDialog('Choose color', self)
        color_pickerd.set_rgba(Gdk.RGBA(*self._color))

        def open_color_chooser(event):
            response_id = color_pickerd.run()
            color_pickerd.hide()

            if response_id == Gtk.ResponseType.OK:
                rgba = color_pickerd.get_rgba()
                self._color = (rgba.red, rgba.green, rgba.blue, rgba.alpha)
                log.debug(f'changed color to {self._color}')

        button.connect('clicked', open_color_chooser)

        header_bar.pack_end(button)

    def on_color_picker_draw(self, widget, cairo_context):
        cairo_context.set_source_rgba(*self._color)
        cairo_context.paint()

    def _setup_undo(self, header_bar):
        button = Gtk.Button(label='Undo')
        button.connect('clicked', self.on_undo)
        header_bar.pack_end(button)

    def on_undo(self, _):
        self._current_tool.undo()

    def _setup_operations(self, header_bar):
        operations_box = Gtk.ButtonBox(orientation=Gtk.Orientation.HORIZONTAL)

        save_button = Gtk.Button(label='Save')
        save_button.connect('clicked', self.save_to_file)
        operations_box.add(save_button)

        clipboard_button = Gtk.Button(label='To clipboard')
        clipboard_button.connect('clicked', self.copy_to_clipboard)
        operations_box.add(clipboard_button)

        header_bar.pack_start(operations_box)

    def copy_to_clipboard(self, widget):
        for tool in self._tools:
            self._image_context.set_source_surface(tool.surface)
            self._image_context.paint()

        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_image(
            Gdk.pixbuf_get_from_surface(self._image_context.get_target(), 0, 0, self._image_rect.width,
                                        self._image_rect.height))
        log.debug('saved annotated image to clipboard')

    def save_to_file(self, widget):
        for tool in self._tools:
            self._image_context.set_source_surface(tool.surface)
            self._image_context.paint()

        self._image_context.get_target().write_to_png(self._filename)
        log.debug(f'saved annotated image to {self._filename}')

    def _setup_event_box(self):
        overlay = Gtk.Overlay()
        overlay.add(self._drawing_area)
        event_box = Gtk.EventBox()
        overlay.add_overlay(event_box)
        event_box.add(self._annotation_area)
        event_box.connect('button_press_event', self.on_mouse_press)
        event_box.connect('button_release_event', self.on_mouse_release)
        event_box.connect('motion_notify_event', self.on_mouse_move)
        self.add(overlay)

    def on_mouse_press(self, widget, event):
        self._current_tool.on_mouse_press(event, self._color)

    def on_mouse_release(self, widget, event):
        self._current_tool.on_mouse_release(event)
        new_surface = self._current_tool.update_surface(self._image_context)
        self._update_image_surface(new_surface)

    def on_mouse_move(self, widget, event):
        log.debug(f'{event.x} {event.y}')
        self._current_tool.on_mouse_move(event)
