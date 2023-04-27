import os, re, shutil, math
import numpy as np

try:
    import rasterio
except ImportError:
    raise ImportError("`rasterio` is required for reading the file. Please install it using 'pip install rasterio' or 'conda install -c conda-forge rasterio'")

try:
    from osgeo import gdal, osr, gdalconst
except ImportError:
    raise ImportError("`gdal` is required for reading the file. Please install it using 'pip install gdal' or 'conda install -c conda-forge gdal'")