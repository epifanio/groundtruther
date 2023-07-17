import sys
import os


class SolveDependencies():
    def __init__(self):
        'check if pip is installed if not run get_pip and upgrade it'
        self.pip_dir = os.path.dirname(__file__)

    try:
        import pip
    except:
        execfile(os.path.join(self.pip_dir, 'get_pip.py'))
        import pip
        # just in case the included version is old
        pip.main(['install','--upgrade','pip'])
    try:
        import pandas
    except:
        print('pandas is not installed')
        pip.main(['install', 'pandas'])
    try:
        import pyqtgraph
    except:
        print('pyqtgraph is not installed')
        pip.main(['install', 'pyqtgraph'])
    # try:
    #     import pyopengl
    # except:
    #     print('pyopengl is not installed')
    #     pip.main(['install', 'pyopengl'])
    try:
        import pydantic
    except:
        print('pydantic is not installed')
        pip.main(['install', 'pydantic'])
    try:
        import starlette
    except:
        print('starlette is not installed')
        pip.main(['install', 'starlette'])
    try:
        import skimage
    except:
        print('scikit-image is not installed')
        pip.main(['install', 'scikit-image'])
    try:
        import plotnine
    except:
        print('plotnine is not installed')
        pip.main(['install', 'plotnine'])
    try:
        import pyarrow
    except:
        print('pyarrow is not installed')
        pip.main(['install', 'pyarrow'])
    try:
        import numba
    except:
        print('numba is not installed')
        pip.main(['install', 'numba'])
    try:
        import simplekml
    except:
        print('simplekml is not installed')
        pip.main(['install', 'simplekml'])
    try:
        import geojson
    except:
        print('geojson is not installed')
        pip.main(['install', 'geojson'])