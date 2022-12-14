# Scrann - Screenshot annotator

Simple screenshot grabber with annotation capabilities.

<a href="screenshot.png">
    <img src="screenshot.png" alt="Demo screenshot" style="width: 300px;"/>
</a>

## How to install

### Requirements:

- Gnome 43
- Flatpak
- Python >= 3.9
- Poetry

Run `poetry install`

### Run without flatpak

```shell
poetry run scrann
```

### Run as flatpak

```shell
flatpak install org.gnome.Sdk/x86_64/43
./flatpak-local-install.sh
```

After installing Scrann should appear in your Gnome application menus.

If you want to run it via command line:

```shell
flatpak run io.github.bjorndown.scrann
```

## To-do

- smooth pen
- text tool
