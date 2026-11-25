"""Shared grid-cell lookup for the regional TopoPyScale comparison notebooks."""
from pathlib import Path
import os

import numpy as np
import pandas as pd
from pyproj import Transformer
import rasterio
import xarray as xr

RUN = Path(os.environ.get(
    'JIF_TOPOPYSCALE_RUN', '/home/cassie/python/models/run_topopyscale/icefield_domain/clfg_test'))
ARCHIVE = Path('/hdd/snow_hydrology/hrrrak/icefield_domain/netcdf')
MOSAIC = Path('/hdd/snow_hydrology/DEMs/ArcticDEM_edits/icefield_domain/jif_mosaic')
SITE_FILE = Path(__file__).resolve().parents[1] / 'sites/clfg/site_info.txt'
ALASKA_GRID = '+proj=stere +lat_0=90 +lat_ts=60 +lon_0=-135 +R=6371229'
RESOLUTIONS = (1000, 500, 250, 100, 50, 20)


def site():
    info = dict(line.split(': ', 1) for line in SITE_FILE.read_text().splitlines())
    lat, lon = (float(info[key].split('(')[-1].rstrip(')')) for key in ('Latitude', 'Longitude'))
    x, y = Transformer.from_crs(4326, 32608, always_xy=True).transform(lon, lat)
    with rasterio.open(MOSAIC / 'jif_tiles_utm8n_2m.vrt') as dem:
        value = next(dem.sample([(x, y)], masked=True))[0]
        if np.ma.is_masked(value) or not np.isfinite(value):
            raise ValueError('CLFG reference elevation is missing in ArcticDEM')
    return lon, lat, x, y, float(value)


def edges(values):
    spacing = np.median(np.diff(values))
    return np.r_[values - spacing / 2, values[-1] + spacing / 2]


def index(values, target):
    i = int(np.abs(values - target).argmin())
    boundary = edges(values)
    if not min(boundary[i:i+2]) <= target <= max(boundary[i:i+2]):
        raise ValueError('CLFG falls outside the grid')
    return i


def raw_path(year):
    return ARCHIVE / f'hrrrak_merged_grib_f567_WY{year}_raw.nc'


def raw_geometry(ds):
    """Return native cell edges in the native model projection."""
    proj = Transformer.from_crs(4326, ALASKA_GRID, always_xy=True)
    x, y = proj.transform(ds.longitude.values, ds.latitude.values)
    return x[0], y[:, 0]


def lookup(year, resolutions=RESOLUTIONS):
    lon, lat, east, north, reference = site()
    with xr.open_dataset(raw_path(year)) as raw:
        x, y = raw_geometry(raw)
        sx, sy = Transformer.from_crs(4326, ALASKA_GRID, always_xy=True).transform(lon, lat)
        row, col = index(y, sy), index(x, sx)
        to_utm = Transformer.from_crs(ALASKA_GRID, 32608, always_xy=True)
        cx, cy = to_utm.transform(x[col], y[row])
        records = [dict(grid='Native HRRR-AK', resolution_m=3000, row=row, col=col,
                        cell_id=-1, center_x_m=cx, center_y_m=cy,
                        elevation_m=float(raw.orog.isel(time=0, y=row, x=col)))]
    for res in resolutions:
        path = RUN / f'WY{year}/{res}m/terrain.nc'
        if not path.exists():
            raise FileNotFoundError(f'Terrain grid is still pending: {path}')
        with xr.open_dataset(path) as dem:
            row, col = index(dem.y.values, north), index(dem.x.values, east)
            cell = int(dem.cell_id.isel(y=row, x=col))
            if cell < 0:
                raise ValueError(f'CLFG grid cell has no forcing at {res} m')
            records.append(dict(grid=f'TopoPyScale {res:g} m', resolution_m=res,
                                row=row, col=col, cell_id=cell,
                                center_x_m=float(dem.x[col]), center_y_m=float(dem.y[row]),
                                elevation_m=float(dem.elevation.isel(y=row, x=col))))
    result = pd.DataFrame(records).set_index('grid')
    result['reference_elevation_m'] = reference
    result['cell_minus_reference_m'] = result.elevation_m - reference
    result['hypothetical_6_K_km_adjustment_K'] = .006 * result.cell_minus_reference_m
    result['water_year'] = year
    return result
