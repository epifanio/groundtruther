from pydantic import AnyUrl, BaseModel, DirectoryPath, FilePath, IPvAnyAddress
from typing import Optional, Union


class HabCam(BaseModel):
    """docstring"""

    imagepath: DirectoryPath
    imagemetadata: FilePath
    imageannotation: Optional[FilePath] = None


class Mbes(BaseModel):
    """docstring"""

    soundings: Optional[FilePath] = None


class Export(BaseModel):
    """docstring"""

    kmldir: Optional[DirectoryPath] = None
    # vrtdir: Optional[DirectoryPath] = None


class Processing(BaseModel):
    """docstring"""
    gpu_avaibility: bool = False
    grass_api_endpoint: Optional[AnyUrl] = None

# class Mapviewer(BaseModel):
#     """docstring"""

#     basemap: Optional[AnyUrl] = None


class Filesystem(BaseModel):
    """docstring"""

    filemanager: Optional[FilePath] = None


class HabcamSettings(BaseModel):
    """docstring"""

    HabCam: Union[HabCam]
    Mbes: Mbes
    Export: Union[Export]
    # Mapviewer: Mapviewer
    Processing: Union[Processing]
    Filesystem: Filesystem
