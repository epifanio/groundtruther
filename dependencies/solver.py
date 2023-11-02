import sys
import os


class SolveDependencies():
    def __init__(self):
        'check if pip is installed if not run get_pip and upgrade it'
        self.pip_dir = os.path.dirname(__file__)

        try:
            import pandas
        except:
            self.install_package('pandas')
        try:
            import pyqtgraph
        except:
            self.install_package('pyqtgraph')
        try:
            import pyopengl
        except:
            self.install_package('pyopengl')
        try:
            import geojson
        except:
            self.install_package('geojson')
        try:
            import pydantic
        except:
            self.install_package('pydantic')
        try:
            import starlette
        except:
            self.install_package('starlette')
        try:
            import skimage
        except:
            self.install_package('skimage')
        try:
            import plotnine
        except:
            self.install_package('plotnine')
        try:
            import pyarrow
        except:
            self.install_package('pyarrow')
        try:
            import numba
        except:
            self.install_package('numba')
        try:
            import simplekml
        except:
            self.install_package('simplekml')

    def install_package(self, missing_package):

        try:
            print(f'{missing_package} is not installed')
            exec(open(os.path.join(self.pip_dir, 'get-pip.py')).read())
            import pip
        except:
            try:
                #raise RuntimeError(f"1 {self.pip_dir}\n2 {os.path.join(self.pip_dir, 'get_pip.py')}")
                exec(open(os.path.join(self.pip_dir, 'get_pip.py')).read())
                import pip
                # just in case the included version is old
                pip.main(['install','--upgrade','pip'])
            except Exception as e:
                raise RuntimeError(f'ERROR solving dependencies! Missing package: "{missing_package}"\n Could not install pip to solve this dependency because of the following error:\n---\n "{e}" \n---\n\n Try installing "{missing_package}" manually.')

        pip.main(['install', missing_package])


if __name__ == '__main__':
    SolveDependencies()
