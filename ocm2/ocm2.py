"""Main module."""

import os, shutil
from osgeo import gdal, osr

def ExportSubdatasets(path, hdf_file):
    
    '''
    This function takes the folder path and the HDF file as input and exports individual layers to TIFF (named GeoTIFF)
    
    Parameters:
    path (str): Path to the folder containing the HDF file
    hdf_file (str): Name of the HDF file

    Returns:
    opf_tif (str): Path to the folder containing the exported TIFF files. The folder is named GeoTiff. The layers are not georeferenced.
    
    '''
    opf_tif = os.path.join(path, 'GeoTiff')
    if os.path.exists(opf_tif):
        shutil.rmtree(opf_tif)
    os.makedirs(opf_tif)
    
    inp_hdf = os.path.join(path, hdf_file)
    hdf_ds = gdal.Open(inp_hdf, gdal.GA_ReadOnly)
    subdatasets = hdf_ds.GetSubDatasets()
    
    for i in range(0, len(subdatasets)):
        subdataset_name = subdatasets[i][0]
        band_ds = gdal.Open(subdataset_name, gdal.GA_ReadOnly)
        band_path = os.path.join(opf_tif, 'band{0}.TIF'.format(i))
        if band_ds.RasterCount > 1:
            for j in range(1,band_ds.RasterCount + 1):
                band = band_ds.GetRasterBand(j)
                band_array = band.ReadAsArray()
        else:
            band_array = band_ds.ReadAsArray()
        
        out_ds = gdal.GetDriverByName('GTiff').Create(band_path,
                                                      band_ds.RasterXSize,
                                                      band_ds.RasterYSize,
                                                      1,
                                                      gdal.GDT_Float64,
                                                      ['COMPRESS=LZW', 'TILED=YES'])
        
        
        out_ds.SetGeoTransform(band_ds.GetGeoTransform())
        out_ds.SetProjection(band_ds.GetProjection())
        out_ds.GetRasterBand(1).WriteArray(band_array)
        out_ds.GetRasterBand(1).SetNoDataValue(-32768)
        
    out_ds = None
        
    return opf_tif

def metaInfo(path, hdf_file):

    '''
    This function takes the folder path and the HDF file as input and returns the metadata of the HDF file.

    Parameters:
    path (str): Path to the folder containing the HDF file
    hdf_file (str): Name of the HDF file

    Returns:
    ulx, uly (float): Upper left corner coordinates
    urx, ury (float): Upper right corner coordinates
    blx, bly (float): Lower left corner coordinates
    brx, bry (float): Lower right corner coordinates
    sun_elev (float): Sun elevation angle
    
    '''
    
    inp = gdal.Open(os.path.join(path, hdf_file))
    meta = inp.GetMetadata()
    
    ulx, uly = float(meta['Upper Left Longitude']), float(meta['Upper Left Latitude'])
    urx, ury = float(meta['Upper Right Longitude']), float(meta['Upper Right Latitude'])
    blx, bly = float(meta['Lower Left Longitude']), float(meta['Lower Left Latitude'])
    brx, bry = float(meta['Lower Right Longitude']), float(meta['Lower Right Latitude'])
    
    sun_elev = float(meta['Sun Elevation Angle'])
    
    return (ulx,  uly), (urx, ury), (brx, bry), (blx, bly), (sun_elev)

def GetExtent(ds):
    
    ''' 
    Return list of corner coordinates from a gdal Dataset 
    
    Parameters:
    ds (gdal.Dataset): A gdal Dataset [something like: ds = gdal.Open('path/to/file.tif')]

    Returns:
    ul, ur, lr, ll (tuple): Upper left, upper right, lower right, lower left corner coordinates
    
    '''
    
    xmin, xpixel, _, ymax, _, ypixel = ds.GetGeoTransform()
    width, height = ds.RasterXSize, ds.RasterYSize
    xmax = xmin + width * xpixel
    ymin = ymax + height * ypixel

    return (xmin, ymax), (xmax, ymax), (xmax, ymin), (xmin, ymin)

def Georeference(inpf, gtif, meta, opf_ref):

    '''
    This function takes the folder path and the GeoTIFF file as input and georeferences the GeoTIFF file.

    Parameters:
    inpf (str): Path to the folder containing the GeoTIFF file
    gtif (str): Name of the GeoTIFF file
    meta (tuple): Metadata of the HDF file. Returned by `metaInfo` function.
    opf_ref (str): Path to the folder containing the georeferenced GeoTIFF file. Inherited from `do_georef` function.

    Returns:
    out_file (str): Path to the georeferenced GeoTIFF file. 
    The file is named as the original GeoTIFF file with _georef.TIF appended to it. 
    
    '''
    
    inp_file = os.path.join(inpf, gtif)
    band_tif = gdal.Open(inp_file)
    ext = GetExtent(band_tif)
    
    ext_pos = [(abs(val[0]), abs(val[1])) for val in ext]

    out_file = os.path.join(opf_ref, os.path.basename(gtif).split('.')[0] + '_georef.TIF')
    shutil.copy(inp_file, out_file)
    ds = gdal.Open(out_file, gdal.GA_Update)
    sr = osr.SpatialReference()
    sr.ImportFromEPSG(4326) 
    
    
    '''
    Enter the GCPs
    Format: [map x-coordinate(longitude)], [map y-coordinate (latitude)], [elevation],
    [image column index(x)], [image row index (y)]
    If map pixel is negative, multiply it with -1 to make positive since GDAL can't handle negative pixel position that well.
    
    '''
    
    gcps = [gdal.GCP(meta[0][0], meta[0][1], 0, ext_pos[0][0], ext_pos[0][1]), 
            gdal.GCP(meta[1][0], meta[1][1], 0, ext_pos[1][0], ext_pos[1][1]),
            gdal.GCP(meta[2][0], meta[2][1], 0, ext_pos[2][0], ext_pos[2][1]), 
            gdal.GCP(meta[3][0], meta[3][1], 0, ext_pos[3][0], ext_pos[3][1])]
    
    ds.SetGCPs(gcps, sr.ExportToWkt())
    ds = None
    
    return 'Done'

def do_georef(geo_tif, meta, opf_georef):

    '''
    This function takes the folder path and the GeoTIFF files within it as input and georeferences the GeoTIFF file.

    Parameters:
    geo_tif (str): Path to the folder containing the GeoTIFF files
    meta (tuple): Metadata of the HDF file.
    opf_georef (str): Path to the folder containing the georeferenced GeoTIFF file. The folder is named GeoTiff_ref

    Returns:
    None
    
    '''
    
    original = os.listdir(geo_tif)
    gtif = list(filter(lambda x: x.endswith(("TIF", "tif", "img")), original))
    for band_name in gtif:
        Georeference(geo_tif, band_name, meta, opf_georef)
        
    return None

def calc_toa(rad, sun_elev, band_no):

    '''
    This function takes the radiance values and the sun elevation angle as input and converts the radiance values to TOA reflectance.
    Parameters:
    rad (numpy.ndarray): Radiance values
    sun_elev (float): Sun elevation angle. Returned by `metaInfo` function.
    band_no (int): Band number. 

    Returns:
    toa_reflectance (numpy.ndarray): TOA reflectance values
    
    '''

    esol = [1.72815, 1.85211, 1.9721, 1.86697, 1.82781, 1.65765, 1.2897, 0.952073]
    toa_reflectance = (np.pi * 1 * rad * 10) / (esol[band_no] * 1000 * math.sin(math.radians(sun_elev)))
    return toa_reflectance

def toa_convert(inpf, inp_name, opf, sun_elev):

    '''
    This function takes the folder path and the GeoTIFF files within it as input and converts the radiance values to TOA reflectance values.

    Parameters:
    inpf (str): Path to the folder containing the GeoTIFF files
    inp_name (str): Name of the GeoTIFF file
    opf (str): Path to the folder containing the TOA reflectance GeoTIFF file. 

    Returns:
    None
    
    '''
    
    band_no = int(''.join(list(filter(str.isdigit, inp_name.split('.')[0].split('_')[0]))))
    with rasterio.open(os.path.join(inpf, inp_name)) as (r):
        rad = r.read(1).astype('float32')
        profile = r.profile
    
    toa = calc_toa(rad, sun_elev, band_no)
    toa[toa < 0] = 0.0
    toa[toa > 2] = 0.0   
    op_name = os.path.basename(inp_name).split('.')[0] + '.TIF'
    with (rasterio.open)((os.path.join(opf, op_name)), 'w', **profile) as (dataset):
        dataset.write(toa, 1)
    dataset.close()
        
    return 'done'

def do_ref(opf_tif, meta, opf_ref):

    '''
    This function takes the folder path and the GeoTIFF files within it as input and converts the radiance values to TOA reflectance values.

    Parameters:
    opf_tif (str): Path to the folder containing the GeoTIFF files
    meta (tuple): Metadata of the HDF file.
    opf_ref (str): Path to the folder containing the TOA reflectance GeoTIFF file.

    Returns:
    None    

    '''
    
    original = os.listdir(opf_tif)
    gtif = list(filter(lambda x: x.endswith(("TIF", "tif", "img")), original))
    for band_name in gtif:
        if (int(''.join(list(filter(str.isdigit, band_name.split('.')[0].split('_')[0]))))) <= 7:
            toa_convert(opf_tif, band_name, opf_ref, meta[4])
        else:
            shutil.copy(os.path.join(opf_tif, band_name), os.path.join(opf_ref, band_name))
            
    return None