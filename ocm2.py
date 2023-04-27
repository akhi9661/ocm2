from ocm2 import run_ocm2
import argparse

def main():

    print('\n------------------------- OCM-2 HDF file processing -----------------------------')
    print('This python package extracts subdatasets from OCM-2 HDF file, georeference them and exports them to GeoTIFF. \nThe package also creates a cloud mask layer.')
    print('The package requires the following inputs:')
    print('1. Path to the folder containing the HDF files [e.g. C:/Users/.../HDF_files/]')
    print('2. Name of the HDF file [e.g. O2_26APR2021_009_011_GAN_L1B_ST_S.hdf]')
    print('----------------------------------------------------------------------------------\n')

    hdf_folder = input('Enter the path to the folder containing the HDF files: ')
    hdf_file = input('Enter the name of the HDF file: ')
    print('\nProcessing...')

    output_folder = run_ocm2(path = hdf_folder, hdf_file = hdf_file)

    print('Done! The output files are saved in the following folder: ' + output_folder)


if __name__ == "__main__":

    main()