import os
import sys
from abc import abstractmethod
from datetime import datetime
import logging
from typing import Tuple, Union

from pydbus import SessionBus
import cairo
import gi

gi.require_version('Gtk', '3.0')
from gi.repository import GLib, Gtk, Gio, Gdk

logging.basicConfig()
log = logging.getLogger('scratt')
log.setLevel('DEBUG')


def get_screenshot():
    bus = SessionBus()
    screenshot = bus.get('org.gnome.Shell.Screenshot')

    path = os.getenv('HOME', default='/tmp')
    timestamp = datetime.isoformat(datetime.now())
    expected_filename = os.path.join(path, 'Pictures', f'screenshot-{timestamp}.png')

    area = screenshot.SelectArea()
    success, expected_filename = screenshot.ScreenshotArea(*area, True, expected_filename)

    if success:
        return expected_filename

    raise RuntimeError('could not capture screenshot')


def file_exists(filename):
    try:
        os.stat(filename)
        return True
    except FileNotFoundError:
        log.warning(f'{filename} not found, capturing new screenshot')
        return False


class Tool:
    label: str

    @abstractmethod
    def on_mouse_press(self, event):
        pass

    @abstractmethod
    def on_mouse_release(self, event):
        pass

    @abstractmethod
    def on_mouse_move(self, event):
        pass


class Rectangle(Tool):
    _start_point: Union[Tuple[int, int], None]
    _end_point: Union[Tuple[int, int], None]

    def __init__(self, image_rect):
        self.label = 'Rectangle'
        self._rectangles = []
        self._start_point = None
        self._end_point = None
        self._color = (0.6, 0.6, 0.6)
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(image_rect.width), int(image_rect.height))
        self._context = cairo.Context(self.surface)

    def _draw(self):
        self._context.set_operator(cairo.Operator.CLEAR)
        self._context.paint()
        self._context.set_operator(cairo.Operator.OVER)
        self._context.set_source_rgb(*self._color)

        if self._start_point:
            self._draw_rectangle(self._start_point, self._end_point)

        for rect in self._rectangles:
            self._draw_rectangle(rect[0], rect[1])

    def _draw_rectangle(self, start_point, end_point):
        width = end_point[0] - start_point[0]
        height = end_point[1] - start_point[1]
        self._context.rectangle(*start_point, width, height)
        self._context.stroke()

    def on_mouse_press(self, event):
        self._start_point = (event.x, event.y)
        self._end_point = self._start_point

    def on_mouse_release(self, event):
        self._end_point = (event.x, event.y)
        self._rectangles.append((self._start_point, self._end_point))
        self._start_point = None
        self._end_point = None
        self._draw()

    def on_mouse_move(self, event):
        self._end_point = (event.x, event.y)
        self._draw()


class Pen(Tool):
    def __init__(self, image_rect):
        self.label = 'Pen'
        self._points = []
        self._color = (1, 0, 0)
        self._line_width = 3
        self.surface = cairo.RecordingSurface(cairo.CONTENT_COLOR_ALPHA, image_rect)
        self._context = cairo.Context(self.surface)

    def on_mouse_press(self, event):
        self._context.set_source_rgb(*self._color)
        self._context.set_line_width(self._line_width)

    def on_mouse_release(self, event):
        log.debug(f'stop drawing, recorded {len(self._points)} points')
        del self._points[:]

    def on_mouse_move(self, event):
        self._points.append((event.x, event.y))
        self._draw()

    def _draw(self):
        for i in range(len(self._points)):
            self._context.move_to(*self._points[i])

            if i + 1 < len(self._points):
                self._context.line_to(*self._points[i + 1])
                self._context.stroke()


class Main(Gtk.Window):
    _current_tool: Tool

    def __init__(self, filename):
        Gtk.Window.__init__(self, title='Screenshot annotator')
        self._image_surface = None

        self.offset = [0, 0]

        self._setup_image_surface(filename)
        self._tools = [Pen(self._image_rect), Rectangle(self._image_rect)]
        self._current_tool = None
        self._setup_event_box()
        self._setup_header_bar()

        self.set_border_width(10)
        self.set_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect('delete-event', Gtk.main_quit)
        self.show_all()
        GLib.timeout_add(50, self._tick)

    def _tick(self):
        self._annotation_area.queue_draw()
        return True

    def _setup_image_surface(self, filename):
        self._image_surface = cairo.ImageSurface.create_from_png(filename)
        self._image_rect = cairo.Rectangle(0, 0, self._image_surface.get_width(), self._image_surface.get_height())
        self.set_default_size(self._image_rect.width, self._image_rect.height)

        self._image_context = cairo.Context(self._image_surface)
        self._image_context.set_source_rgba(0, 0, 0, 0)
        self._image_context.save()

        self._drawing_area = Gtk.DrawingArea()
        self._drawing_area.connect('draw', self.on_draw)

        self._annotation_area = Gtk.DrawingArea()
        self._annotation_area.connect('draw', self.on_draw_annotations)

    def on_draw_annotations(self, widget, cairo_context):
        for tool in self._tools:
            cairo_context.set_source_surface(tool.surface)
            cairo_context.paint()

    def on_draw(self, widget, cairo_context):
        cairo_context.set_source_surface(self._image_surface, *self.offset)
        cairo_context.paint()

    def _setup_header_bar(self):
        header_bar = Gtk.HeaderBar()
        header_bar.set_show_close_button(True)
        header_bar.props.title = 'Screenshot annotator'
        self.set_titlebar(header_bar)
        self._setup_tools(header_bar)

    def _setup_tools(self, header_bar):
        self._tool_box = box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        Gtk.StyleContext.add_class(box.get_style_context(), 'linked')

        for tool in self._tools:
            button = Gtk.ToggleButton(label=tool.label)
            button.connect('clicked', self._change_tool(tool))
            self._tool_box.add(button)
            if tool.label == self._tools[0].label:
                button.clicked()

        header_bar.pack_end(self._tool_box)

    def _change_tool(self, tool):
        def cb(widget):
            if widget.get_active():
                log.debug(f'using {tool.label}')
                self._current_tool = tool

        return cb

    def _setup_event_box(self):
        overlay = Gtk.Overlay()
        overlay.add(self._drawing_area)
        event_box = Gtk.EventBox()
        overlay.add_overlay(event_box)
        event_box.add(self._annotation_area)
        event_box.connect('button_press_event', self._on_mouse_press)
        event_box.connect('button_release_event', self._on_mouse_release)
        event_box.connect('motion_notify_event', self._on_mouse_move)
        self.add(overlay)

    def _on_mouse_press(self, widget, event):
        self._current_tool.on_mouse_press(event)

    def _on_mouse_release(self, widget, event):
        self._current_tool.on_mouse_release(event)

    def _on_mouse_move(self, widget, event):
        self._current_tool.on_mouse_move(event)


try:
    filename = sys.argv[1] if len(sys.argv) > 1 and file_exists(sys.argv[1]) else get_screenshot()
    log.info(f'opening {filename}')
    win = Main(filename)
    Gtk.main()
except KeyboardInterrupt:
    log.info('bye')
