#!/usr/bin/sh
set -o errexit
poetry build
flatpak-builder --force-clean --user --disable-cache --install build-dir io.github.bjorndown.scrann.yml
