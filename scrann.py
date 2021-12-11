import gi

from scrann.dbus import get_screenshot, notifier
from scrann.log import log
from scrann.window import Main

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk


def main():
    try:
        get_screenshot(lambda filename: Main(filename))
        Gtk.main()
    except KeyboardInterrupt:
        log.info('bye')
    finally:
        notifier.clean_up()


if __name__ == '__main__':
    main()
