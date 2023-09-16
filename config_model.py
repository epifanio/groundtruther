from pydantic import AnyUrl, BaseModel, DirectoryPath, FilePath, IPvAnyAddress
from typing import Union


class HabCam(BaseModel):
    """docstring"""

    imagepath: DirectoryPath
    imagemetadata: FilePath
    imageannotation: FilePath


class Mbes(BaseModel):
    """docstring"""

    soundings: FilePath = None


class Export(BaseModel):
    """docstring"""

    kmldir: DirectoryPath = None
    # vrtdir: DirectoryPath = None


class Processing(BaseModel):
    """docstring"""
    gpu_avaibility: bool = False
    grass_api_endpoint: AnyUrl = None

# class Mapviewer(BaseModel):
#     """docstring"""

#     basemap: AnyUrl = None


class Filesystem(BaseModel):
    """docstring"""

    filemanager: FilePath = None


class HabcamSettings(BaseModel):
    """docstring"""

    HabCam: Union[HabCam]
    Mbes: Mbes
    Export: Union[Export]
    # Mapviewer: Mapviewer
    Processing: Union[Processing]
    Filesystem: Filesystem
