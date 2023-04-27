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



def ExportSubdatasets(path, hdf_file):

    """   
    This function takes the folder path and the HDF file as input and exports individual layers to TIFF (named GeoTIFF)
    
    Parameters:
        path (str): Path to the folder containing the HDF file.
        hdf_file (str): Name of the HDF file.

    Returns:
        opf_tif (str): Path to the folder containing the GeoTiff files.
        
    """
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
    

def metaInfo(path, hdf_file, input = None):


    """
    This function returns the metadata of the HDF file.

    Parameters:
        path (str): Path to the folder containing the HDF file.
        hdf_file (str): Name of the HDF file.

    Returns:    
        meta (dict): Dictionary containing the metadata of the HDF file. 
    
    """
    
    inp = gdal.Open(os.path.join(path, hdf_file))
    meta = inp.GetMetadata()
    
    ulx, uly = float(meta['Upper Left Longitude']), float(meta['Upper Left Latitude'])
    urx, ury = float(meta['Upper Right Longitude']), float(meta['Upper Right Latitude'])
    blx, bly = float(meta['Lower Left Longitude']), float(meta['Lower Left Latitude'])
    brx, bry = float(meta['Lower Right Longitude']), float(meta['Lower Right Latitude'])
    
    sun_elev = float(meta['Sun Elevation Angle'])
    
    return (ulx,  uly), (urx, ury), (brx, bry), (blx, bly), (sun_elev)
    
def GetExtent(ds):
    
    """
    This function returns the extent of the raster. 

    Parameters:
        ds (object): GDAL dataset object.

    Returns:
        (xmin, ymax), (xmax, ymax), (xmax, ymin), (xmin, ymin) (tuple): Extent of the raster.
       
    """
    
    xmin, xpixel, _, ymax, _, ypixel = ds.GetGeoTransform()
    width, height = ds.RasterXSize, ds.RasterYSize
    xmax = xmin + width * xpixel
    ymin = ymax + height * ypixel

    return (xmin, ymax), (xmax, ymax), (xmax, ymin), (xmin, ymin)


def Georeference(inpf, gtif, meta, opf_ref):

    """
    This function georeferences the GeoTiff files using the metadata of the HDF file.

    Parameters:
        inpf (str): Path to the folder containing the GeoTiff files.
        gtif (str): Name of the GeoTiff file.
        meta (dict): Dictionary containing the metadata of the HDF file.

    Returns:
        opf_ref (str): Path to the folder containing the georeferenced GeoTiff files.

    """
    
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
    
    return opf_ref


def calc_toa(rad, sun_elev, band_no):

    """
    This function calculates the top of atmosphere reflectance.

    Parameters:
        rad (numpy array): Array containing the radiance values.
        sun_elev (float): Sun elevation angle.
        band_no (int): Band number.

    Returns:
        toa_reflectance (numpy array): Array containing the top of atmosphere reflectance values.

    """

    esol = [1.72815, 1.85211, 1.9721, 1.86697, 1.82781, 1.65765, 1.2897, 0.952073]
    toa_reflectance = (np.pi * 1 * rad * 10) / (esol[band_no] * 1000 * math.sin(math.radians(sun_elev)))
    return toa_reflectance

def toa_convert(inpf, inp_name, opf, sun_elev):

    """
    This function converts the radiance values to top of atmosphere reflectance values.

    Parameters:
        inpf (str): Path to the folder containing the GeoTiff files.
        inp_name (str): Name of the GeoTiff file.
        opf (str): Path to the folder containing the output GeoTiff files.
        sun_elev (float): Sun elevation angle.

    Returns:
        opf (str): Path to the folder containing the output GeoTiff files.

    """
    
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
        
    return opf

def list_files(inpf, inp_name, files):

    """
    This function lists the GeoTiff files.

    Parameters:
        inpf (str): Path to the folder containing the GeoTiff files.
        inp_name (str): Name of the GeoTiff file.
        files (list): List containing the GeoTiff files. Empty list at the beginning.

    Returns:
        files (list): List containing the GeoTiff files.

    """
    
    files.append(os.path.join(inpf, inp_name))
    return files
        
    
def sum_toa(filelist):

    """
    This function sums the top of atmosphere reflectance values.

    Parameters:
        filelist (list): List containing the GeoTiff files.

    Returns:
        arr (numpy array): Array containing the sum of the top of atmosphere reflectance values.

    """
    
    with rasterio.open(filelist[0]) as r:
        arr = r.read()
        profile = r.profile
        
    for f in filelist[1:]:
        with rasterio.open(f) as r:
            assert profile == r.profile, 'stopping, file {} and  {} do not have matching profiles'.format(filelist[0], f)
            arr = arr + r.read()

    return (arr)

def toa_other(filelist):

    """
    This function calculates the difference and ratio of the top of atmosphere reflectance values.

    Parameters:
        filelist (list): List containing the GeoTiff files.

    Returns:
        toa_diff (numpy array): Array containing the difference of the top of atmosphere reflectance values.
        toa_ratio (numpy array): Array containing the ratio of the top of atmosphere reflectance values.
        shape (tuple): Tuple containing the shape of the GeoTiff file.
        profile (dict): Dictionary containing the profile of the GeoTiff file.

    """
     
    one, two, seven = [filelist[check] for check in [0,1,6]]
    
    with rasterio.open(one) as r:
        band1 = r.read()
        profile = r.profile
    shape = band1.shape
    with rasterio.open(two) as r:
        band2 = r.read()
    with rasterio.open(seven) as r:
        band7 = r.read()
        
    
    band2[band2 == 0.0] = np.nan
    band7[band7 == 0.0] = np.nan

    toa_diff = band2 - band1
    toa_ratio = band2/band7 

    return (toa_diff, toa_ratio, shape, profile)

def cloudmask_ocm(inpf, filelist):

    """
    This function creates the cloud mask based on Mishra et al. (2018).

    Parameters:
        inpf (str): Path to the folder containing the GeoTiff files.
        filelist (list): List containing the GeoTiff files.

    Returns:
        cldmsk (numpy array): Array containing the cloud mask.

    """
    
    toa_sum = sum_toa(filelist)
    toa_diff, toa_ratio, shape, profile = toa_other(filelist) 
    
    cldmsk = np.zeros(shape, dtype = 'float32')
    cldmsk = np.where(((toa_sum > 2.7) & (toa_ratio > 1.5) & (toa_diff < 0)), 1, 0)
    
    with (rasterio.open)((os.path.join(inpf, 'cloud_mask.TIF')), 'w', **profile) as (dst):
        dst.write(cldmsk)
    dst.close()
    
    return cldmsk


def do_ref(opf_tif, meta, opf_ref):

    """
    This function calls the function that creates the top of atmosphere reflectance GeoTiff files.

    Parameters:
        opf_tif (str): Path to the folder containing the GeoTiff files.
        meta (list): List containing the metadata of the GeoTiff files.
        opf_ref (str): Path to the folder containing the output reflectance GeoTiff files. Temporary folder.

    Returns:
        None

    """
    
    original = os.listdir(opf_tif)
    gtif = list(filter(lambda x: x.endswith(("TIF", "tif", "img")), original))
    for band_name in gtif:
        if (int(''.join(list(filter(str.isdigit, band_name.split('.')[0].split('_')[0]))))) <= 7:
            toa_convert(opf_tif, band_name, opf_ref, meta[4])
        else:
            shutil.copy(os.path.join(opf_tif, band_name), os.path.join(opf_ref, band_name))
            
    return None
    
def do_georef(opf_ref, meta, opf_georef):

    """
    This function calls the function that georeferences the top of atmosphere reflectance GeoTiff files.

    Parameters:
        geo_ref (str): Path to the folder containing the georeferenced GeoTiff files.
        meta (list): List containing the metadata of the HDF files.
        opf_georef (str): Path to the folder containing the output georeferenced GeoTiff files. 

    Returns:
        opf_georef (str): Path to the folder containing the output georeferenced GeoTiff files.

    """
    
    original = os.listdir(opf_ref)
    gtif = list(filter(lambda x: x.endswith(("TIF", "tif", "img")), original))
    for band_name in gtif:
        Georeference(opf_ref, band_name, meta, opf_georef)
        
    return opf_georef
    
def do_cldmsk(opf_ref):

    """
    This function calls the function that creates the cloud mask.

    Parameters:
        opf_ref (str): Path to the folder containing the output georeferenced GeoTiff files.

    Returns:
        None

    """
    
    files = []

    original = os.listdir(opf_ref)
    gtif = list(filter(lambda x: x.endswith(("TIF", "tif", "img")), original))
    for band_name in gtif:
        if (int(''.join(list(filter(str.isdigit, band_name.split('.')[0].split('_')[0]))))) <= 7:
            filelist = list_files(opf_ref, band_name, files)

    cldmsk = cloudmask_ocm(opf_ref, filelist)
    
    return None

def run_ocm2(path, hdf_file):

    """
    This is the main function of the script. It calls all the other functions. 

    Parameters:
        path (str): Path to the folder containing the HDF files.
        hdf_file (str): Name of the HDF file.

    Returns:
        None

    """

    meta = metaInfo(path, hdf_file)
    opf_tif = ExportSubdatasets(path, hdf_file)
    print('Done: Layers converted to GeoTIFF. Wait.')

    opf_ref = os.path.join(path, 'Reflectance')
    if os.path.exists(opf_ref):
        shutil.rmtree(opf_ref)
    os.makedirs(opf_ref)

    opf_georef = os.path.join(path, 'Georeferenced')
    if os.path.exists(opf_georef):
        shutil.rmtree(opf_georef)
    os.makedirs(opf_georef)

    do_ref(opf_tif, meta, opf_ref)
    print('Done: Reflectance conversion. Wait.')
    
    do_cldmsk(opf_ref)
    print('Done: Cloudmasking. Wait.')
    
    opf_georef = do_georef(opf_ref, meta, opf_georef)
    print('Done: Georeferncing')

    if os.path.exists(opf_tif):
        shutil.rmtree(opf_tif)
        
    if os.path.exists(opf_ref):
        shutil.rmtree(opf_ref)

    return opf_georef
