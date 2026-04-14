import numpy as np
import pandas as pd
from qgis.core import Qgis, QgsMapLayer, QgsMessageLog, QgsWkbTypes, QgsVectorFileWriter, QgsCoordinateTransformContext, QgsProject, QgsVectorLayerExporter

import json
import requests
from io import StringIO
import tempfile
import os
from osgeo import ogr, osr
import uuid




def bbox_parser(row, columns, name):
    return {name: [row[i] for i in columns]}


def parse_annotation(annotation_file):
    names = [
        "Detection",
        "Imagename",
        "Frame_Identifier",
        "TL_x",
        "TL_y",
        "BR_x",
        "BR_y",
        "detection_Confidence",
        "Target_Length",
        "Species",
        "Confidence",
    ]
    imageannotation = pd.read_csv(annotation_file, skiprows=[0, 1], names=names)
    imageannotation["Imagename"] = imageannotation["Imagename"].str.replace(
        ".jpg", "", regex=False
    )
    # Ensure numeric columns are actually numeric (CSV may leave them as strings)
    for col in ("TL_x", "TL_y", "BR_x", "BR_y", "Confidence"):
        imageannotation[col] = pd.to_numeric(imageannotation[col], errors="coerce")
    columns = ["TL_x", "BR_y", "BR_x", "BR_y", "BR_x", "TL_y", "TL_x", "TL_y"]
    imageannotation["bbox"] = imageannotation.apply(
        bbox_parser, columns=columns, name="bbox", axis=1
    )
    annotations_by_image = (
        imageannotation.groupby("Imagename")
        .agg({"bbox": list, "Species": list, "Confidence": list})
        .to_dict("index")
    )
    return annotations_by_image


def get_layer_info(layer):
    # Get the active layer
    # layer = iface.activeLayer()
    
    # Check if a layer is active
    if not layer:
        return {"error": "No active layer selected"}
    
    # Initialize the dictionary to hold layer info
    layer_info = {}
    
    # Layer Name
    layer_info['name'] = layer.name()
    
    # Layer Type
    if layer.type() == QgsMapLayer.VectorLayer:
        layer_info['type'] = 'vector'
        
        # Geometry Type
        geom_type = layer.geometryType()
        # print('geom_type: ', geom_type)
        # print('geom_type name : ', geom_type.name)
        # print('geom_type value: ', geom_type.value)
        # print(dir(geom_type))
        layer_info['geometry_type'] = geom_type.name
        
        # Fields
        fields_info = {}
        fields = layer.fields()
        for field in fields:
            fields_info[field.name()] = field.typeName()
        layer_info['fields'] = fields_info
        
        # Number of Features
        layer_info['feature_count'] = layer.featureCount()
        
        
    elif layer.type() == QgsMapLayer.RasterLayer:
        layer_info['type'] = 'raster'
    
    # CRS
    layer_info['crs'] = layer.crs().authid()
    
    # Extent
    extent = layer.extent()
    layer_info['extent'] = {
        'xmin': extent.xMinimum(),
        'xmax': extent.xMaximum(),
        'ymin': extent.yMinimum(),
        'ymax': extent.yMaximum()
    }
    layer_info['data_source'] = layer.source()
    return layer_info


def export_layer_to_geojson(layer, output_path):
    # Get the active layer

    # Check if a layer is active and it's a vector layer
    if not layer or layer.type() != QgsMapLayer.VectorLayer:
        return {"error": "No active vector layer selected"}
    
    # Define the output file path
    output_file = os.path.join(output_path, f"{layer.name()}.geojson")
    
    # Set options for GeoJSON export
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "GeoJSON"
    
    error = QgsVectorFileWriter.writeAsVectorFormat(layer, output_file,
                                                "utf-8", None, "GeoJSON")
    # Check for errors
    if error == QgsVectorFileWriter.NoError:
        return {"success": f"Layer exported successfully to {output_file}"}
    else:
        return {"error": f"Failed to export layer. Error code: {error}"}
    
    

    
def send_layer_as_geojson(layer, api_endpoint):
    # Get the active layer
    # layer = iface.activeLayer()
    
    # Check if a layer is active and it's a vector layer
    if not layer or layer.type() != QgsMapLayer.VectorLayer:
        return {"error": "No active vector layer selected"}
    
    # Create a temporary file to store the GeoJSON
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".geojson")
    temp_file.close()  # Close the file so QGIS can write to it
    
    error = QgsVectorFileWriter.writeAsVectorFormat(layer, temp_file.name,
                                                    "utf-8", layer.crs(), "GeoJSON")
    
    if error == QgsVectorFileWriter.NoError:
        QgsMessageLog.logMessage("convert_to_geojson_using_gdal: write succeeded", 'GroundTruther', Qgis.Info)

    
    # Read the GeoJSON data from the temporary file
    with open(temp_file.name, 'r', encoding='utf-8') as f:
        geojson_data = f.read()
    
    # Clean up the temporary file
    os.remove(temp_file.name)
    
    # Send the GeoJSON string as a JSON payload to the API endpoint
    headers = {'Content-Type': 'application/json'}
    response = requests.post(api_endpoint, data=geojson_data, headers=headers)
    
    # Return the API response
    if response.status_code == 200:
        return {"success": "Layer successfully sent to the API", "response": response.json()}
    else:
        return {"error": f"Failed to send GeoJSON to API. Status code: {response.status_code}", "response": response.text}
    
    
def send_layer_as_geojson_using_gdal_(layer, api_endpoint):
    # Get the active layer
    # layer = iface.activeLayer()
    
    # Check if a layer is active and it's a vector layer
    if not layer or layer.type() != QgsMapLayer.VectorLayer:
        return {"error": "No active vector layer selected"}
    
    # Create a temporary file to store the exported layer
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".gpkg")
    temp_file.close()  # Close the file so GDAL/OGR can write to it
    
    # Export the layer to a temporary file in GeoPackage format
    export_options = {
        'driverName': 'GPKG',
        'layerName': 'exported_layer'
    }
    
    error = QgsVectorFileWriter.writeAsVectorFormat(
        layer,
        temp_file.name,
        "utf-8",
        layer.crs(),
        "GPKG"
    )
    
    if error != QgsVectorFileWriter.NoError:
        os.remove(temp_file.name)  # Clean up the temporary file
        return {"error": f"Failed to export layer to GPKG. Error code: {error}"}
    
    # Open the GeoPackage with GDAL/OGR
    driver = ogr.GetDriverByName('GPKG')
    if driver is None:
        os.remove(temp_file.name)  # Clean up the temporary file
        return {"error": "GDAL does not support GeoPackage format"}
    
    ogr_data_source = driver.Open(temp_file.name, 0)  # 0 means read-only
    if ogr_data_source is None:
        os.remove(temp_file.name)  # Clean up the temporary file
        return {"error": "Failed to open the GeoPackage file with OGR"}
    
    # Create a temporary file to store GeoJSON data
    geojson_temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".geojson")
    geojson_temp_file.close()  # Close the file so GDAL/OGR can write to it
    
    # Convert GeoPackage to GeoJSON
    ogr2ogr_cmd = [
        'ogr2ogr',
        '-f', 'GeoJSON',
        geojson_temp_file.name,
        temp_file.name
    ]
    
    result = os.system(' '.join(ogr2ogr_cmd))
    
    if result != 0:
        os.remove(temp_file.name)
        os.remove(geojson_temp_file.name)
        return {"error": "Failed to convert GeoPackage to GeoJSON using ogr2ogr"}
    
    # Read the GeoJSON data from the temporary file
    with open(geojson_temp_file.name, 'r', encoding='utf-8') as f:
        geojson_data = f.read()
    
    # Clean up the temporary files
    os.remove(temp_file.name)
    os.remove(geojson_temp_file.name)
    
    # Send the GeoJSON string as a JSON payload to the API endpoint
    headers = {'Content-Type': 'application/json'}
    response = requests.post(api_endpoint, data=geojson_data, headers=headers)
    
    # Return the API response
    if response.status_code == 200:
        return {"success": "Layer successfully sent to the API", "response": response.json()}
    else:
        return {"error": f"Failed to send GeoJSON to API. Status code: {response.status_code}", "response": response.text}
    
    
def convert_to_geojson_using_gdal(input_path):
    """Convert a vector file to a GeoJSON string using GDAL/OGR.

    :param input_path: Path to the input vector file.
    :return: GeoJSON string on success, or an error string on failure.

    The function is intentionally limited to conversion only.  Callers that
    need to POST the result to an API endpoint should do so themselves, passing
    the appropriate endpoint URL explicitly.
    """
    tmp_path = uuid.uuid4().hex + ".geojson"

    input_ds = ogr.Open(input_path)
    if input_ds is None:
        return f"Failed to open input file: {input_path}"

    geojson_driver = ogr.GetDriverByName("GeoJSON")
    if geojson_driver is None:
        return "GDAL GeoJSON driver not found"

    output_ds = geojson_driver.CreateDataSource(tmp_path)
    if output_ds is None:
        return f"Failed to create temporary GeoJSON file: {tmp_path}"

    for i in range(input_ds.GetLayerCount()):
        input_layer = input_ds.GetLayerByIndex(i)
        output_layer = output_ds.CreateLayer(
            input_layer.GetName(),
            geom_type=input_layer.GetGeomType(),
        )
        output_layer.CreateFields(input_layer.schema)
        for feature in input_layer:
            output_layer.CreateFeature(feature)

    del output_ds
    del input_ds

    with open(tmp_path, "r", encoding="utf-8") as fh:
        geojson_data = fh.read()

    os.remove(tmp_path)
    return geojson_data
