from setuptools import setup

setup(
    name='scrann',
    version='0.0.1',
    keywords='gtk, gnome, screenshot, graphic, editor',
    py_modules=['scrann'],
    python_requires='>=3.5, <4',
    install_requires=['pydbus', 'pycairo', 'pygobject'],
    entry_points={
        'console_scripts': [
            'scrann=scrann:main',
        ],
    },
)
