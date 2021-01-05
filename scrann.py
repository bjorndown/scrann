import os
import sys
from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Tuple, Union, List

from pydbus import SessionBus
import cairo
import gi

gi.require_version('Gtk', '3.0')
from gi.repository import GLib, Gtk, Gio, Gdk

logging.basicConfig()
log = logging.getLogger('scrann')
log.setLevel('DEBUG')

_dbus = None


def _get_dbus():
    global _dbus
    if _dbus is None:
        _dbus = SessionBus()
    return _dbus


def _notify(msg, replaces_id=0):
    notifications = _get_dbus().get('.Notifications')
    return notifications.Notify('scrann', replaces_id, 'dialog-error', 'Scrann', msg, [], {}, 50)


def retry(fn, max_tries: int):
    num_try = 0
    notification_id = 0
    while num_try < max_tries:
        try:
            return fn()
        except Exception as e:
            notification_id = _notify('Selecting area failed, try again', notification_id)
            log.debug(f'try {num_try} failed with ({str(e)}), retrying')
            num_try = num_try + 1
            if num_try == max_tries:
                notification_id = _notify(f'Selecting area failed {max_tries} times, giving up', notification_id)
                raise e


def get_screenshot():
    screenshot = _get_dbus().get('org.gnome.Shell.Screenshot')

    path = os.getenv('HOME', default='/tmp')
    timestamp = datetime.isoformat(datetime.now())
    expected_filename = os.path.join(path, 'Pictures', f'screenshot-{timestamp}.png')

    def _take_screenshot():
        area = screenshot.SelectArea()
        return screenshot.ScreenshotArea(*area, True, expected_filename)

    success, expected_filename = retry(_take_screenshot, 3)

    if success:
        return expected_filename

    raise RuntimeError('could not capture screenshot')


def file_exists(filename):
    try:
        os.stat(filename)
        return True
    except FileNotFoundError:
        log.warning(f'File \'{filename}\' not found, capturing new screenshot')
        return False


class Tool:
    label: str

    @abstractmethod
    def on_mouse_press(self, event, color):
        pass

    @abstractmethod
    def on_mouse_release(self, event):
        pass

    @abstractmethod
    def on_mouse_move(self, event):
        pass

    @abstractmethod
    def undo(self):
        pass


@dataclass
class R:
    points: Tuple[Tuple[int, int], Tuple[int, int]]
    color: Tuple[float, float, float, float]


class Rectangle(Tool):
    _start_point: Union[Tuple[int, int], None]
    _end_point: Union[Tuple[int, int], None]

    def __init__(self, image_rect):
        self.label = 'Rectangle'
        self._rectangles = []
        self._start_point = None
        self._end_point = None
        self._color = None
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(image_rect.width), int(image_rect.height))
        self._context = cairo.Context(self.surface)

    def _draw(self):
        self._context.set_operator(cairo.Operator.CLEAR)
        self._context.paint()
        self._context.set_operator(cairo.Operator.OVER)

        for rect in self._rectangles:
            self._draw_rectangle(rect.points[0], rect.points[1], rect.color)

        if self._start_point:
            self._draw_rectangle(self._start_point, self._end_point, self._color)

    def _draw_rectangle(self, start_point, end_point, color):
        self._context.set_source_rgba(*color)
        width = end_point[0] - start_point[0]
        height = end_point[1] - start_point[1]
        self._context.rectangle(*start_point, width, height)
        self._context.stroke()

    def on_mouse_press(self, event, color):
        self._color = color
        self._start_point = (event.x, event.y)
        self._end_point = self._start_point

    def on_mouse_release(self, event):
        self._end_point = (event.x, event.y)
        self._rectangles.append(R((self._start_point, self._end_point), self._color))
        self._start_point = None
        self._end_point = None
        self._draw()

    def on_mouse_move(self, event):
        self._end_point = (event.x, event.y)
        self._draw()

    def undo(self):
        if len(self._rectangles) > 0:
            undone_rect = self._rectangles.pop()
            log.debug(f'undid rect {undone_rect}')
            self._draw()


@dataclass
class Path:
    points: List[Tuple[float, float]]
    color: Tuple[float, float, float, float]


class Pen(Tool):
    def __init__(self, image_rect):
        self.label = 'Pen'
        self._paths = []
        self._path = []
        self._color = None
        self._line_width = 3
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(image_rect.width), int(image_rect.height))
        self._context = cairo.Context(self.surface)

    def on_mouse_press(self, event, color):
        self._color = color
        self._context.set_line_width(self._line_width)

    def on_mouse_release(self, event):
        log.debug(f'stop drawing, recorded {len(self._path)} points')
        self._paths.append(Path(list(self._path), self._color))
        del self._path[:]

    def on_mouse_move(self, event):
        self._path.append((event.x, event.y))
        self._draw()

    def _draw(self):
        self._context.set_operator(cairo.Operator.CLEAR)
        self._context.paint()
        self._context.set_operator(cairo.Operator.OVER)

        for path in self._paths:
            self._draw_path(path.points, path.color)

        self._draw_path(self._path, self._color)

    def _draw_path(self, points, color):
        self._context.set_source_rgba(*color)
        for i in range(len(points)):
            self._context.move_to(*points[i])

            if i + 1 < len(points):
                self._context.line_to(*points[i + 1])
                self._context.stroke()

    def undo(self):
        if len(self._paths) > 0:
            self._paths.pop()
            self._draw()


class Main(Gtk.Window):
    _current_tool: Union[Tool, None]

    def __init__(self, filename):
        Gtk.Window.__init__(self, title='Scrann')
        self._image_surface = None
        self._color = (1, 0, 0, 1)
        self._filename = filename

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
        GLib.timeout_add(50, self.redraw)

    def redraw(self):
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
        header_bar.props.title = self._filename
        self.set_titlebar(header_bar)
        self._setup_tools(header_bar)
        self._setup_color(header_bar)
        self._setup_undo(header_bar)
        self._setup_operations(header_bar)

    def _setup_tools(self, header_bar):
        self._tool_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        Gtk.StyleContext.add_class(self._tool_box.get_style_context(), 'linked')

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
        button = Gtk.Button()
        icon = Gio.ThemedIcon(name='undo')
        image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
        button.connect('clicked', self.on_undo)
        button.add(image)
        header_bar.pack_end(button)

    def on_undo(self, _):
        self._current_tool.undo()

    def _setup_operations(self, header_bar):
        operations_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        Gtk.StyleContext.add_class(operations_box.get_style_context(), 'linked')

        save_button = Gtk.Button(label='Save to file')
        save_button.connect('clicked', self.save_to_file)
        operations_box.add(save_button)

        clipboard_button = Gtk.Button(label='Copy to clipboard')
        clipboard_button.connect('clicked', self.copy_to_clipboard)
        operations_box.add(clipboard_button)

        header_bar.pack_start(operations_box)

    def copy_to_clipboard(self, widget):
        for tool in self._tools:
            self._image_context.set_source_surface(tool.surface)
            self._image_context.paint()

        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_image(
            Gdk.pixbuf_get_from_surface(self._image_surface, 0, 0, self._image_rect.width, self._image_rect.height))
        log.debug('saved annotated image to clipboard')

    def save_to_file(self, widget):
        for tool in self._tools:
            self._image_context.set_source_surface(tool.surface)
            self._image_context.paint()

        self._image_surface.write_to_png(self._filename)
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

    def on_mouse_move(self, widget, event):
        self._current_tool.on_mouse_move(event)


def main():
    try:
        filename = sys.argv[1] if len(sys.argv) > 1 and file_exists(sys.argv[1]) else get_screenshot()
        log.info(f'opening {filename}')
        win = Main(filename)
        Gtk.main()
    except KeyboardInterrupt:
        log.info('bye')


if __name__ == '__main__':
    main()
