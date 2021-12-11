import os
import sys

import gi
from pydbus import SessionBus

from scrann.log import log

gi.require_version('Gtk', '3.0')
from gi.repository import GLib

_dbus = None


def _get_dbus():
    global _dbus
    if _dbus is None:
        _dbus = SessionBus()
    return _dbus


class Notifier:
    def __init__(self, dbus):
        self._last_notification_id = 0
        self._notifications = dbus.get('.Notifications')

    def notify(self, msg):
        self._last_notification_id = self._notifications.Notify('scrann', self._last_notification_id, 'dialog-error',
                                                                'Scrann', msg, [], {}, 50)

    def clean_up(self):
        if self._last_notification_id != 0:
            log.debug('closing notifications')
            self._notifications.CloseNotification(self._last_notification_id)


notifier = Notifier(_get_dbus())


def retry(fn, max_tries: int):
    num_try = 0
    while num_try < max_tries:
        try:
            return fn()
        except Exception as e:
            notifier.notify('Selecting area failed, try again')
            log.debug(f'try {num_try} failed with ({str(e)}), retrying')
            num_try = num_try + 1
            if num_try == max_tries:
                notifier.notify(f'Selecting area failed {max_tries} times, giving up')
                raise e


desktop_portal = _get_dbus().get('org.freedesktop.portal.Desktop', object_path='/org/freedesktop/portal/desktop')
parent_window = ''  # TODO ??
desktop_portal.onPropertiesChanged = print


def _get_screenshot():
    def _take_screenshot():
        screenshot_uri = desktop_portal.Screenshot(parent_window, {'interactive': GLib.Variant('b', True)})
        return screenshot_uri

    return retry(_take_screenshot, 3)


def open_uri(uri: str):
    return desktop_portal.OpenURI(parent_window, uri, {})


def file_exists(filename):
    try:
        os.stat(filename)
        return True
    except FileNotFoundError:
        log.warning(f'File \'{filename}\' not found, capturing new screenshot')
        return False


def get_screenshot(start_callback):
    def signal_callback(sender, obj, iface, signal, params):
        [response, results] = params
        print(response, results)
        if response == 0 and 'uri' in results:
            print(f'opening {results["uri"][7:]}')
            filename = results['uri'][7:]  # cairo does not like file://
            start_callback(filename)

    if len(sys.argv) > 1 and file_exists(sys.argv[1]):
        start_callback(sys.argv[1])
    else:
        _get_dbus().subscribe("org.freedesktop.portal.Desktop",
                              "org.freedesktop.portal.Request",
                              "Response", None, None, signal_fired=signal_callback)
        open_uri(_get_screenshot())  # TODO
