"""Compare raw HRRR-AK with the existing CLFG fixed-lapse-rate baseline."""
import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from pyproj import CRS, Transformer
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import rowcol
from rasterio.windows import Window, from_bounds
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sites/radar_sites/scripts'))
from prepare_radar_site_forcing import HRRR, VARIABLES, UNITS, cell_index

DEM = Path('/hdd/snow_hydrology/DEMs/ArcticDEM_edits/icefield_domain/jif_mosaic/jif_tiles_utm8n_2m.vrt')
LAPSE_RATE = 0.006  # K/m, as in the existing CLFG workflow


def terrain(dem, east, north):
    # Common grid edges for the nested 20 and 100 m averages over 6 × 6 km.
    left = np.floor(east / 100) * 100 - 3000
    bottom = np.floor(north / 100) * 100 - 3000
    bounds = (left, bottom, left + 6000, bottom + 6000)
    with rasterio.open(dem) as src:
        if src.crs.to_epsg() != 32608:
            raise ValueError('Expected DEM in EPSG:32608')
        win = from_bounds(*bounds, transform=src.transform)
        if (win.col_off < 0 or win.row_off < 0 or win.col_off + win.width > src.width
                or win.row_off + win.height > src.height):
            raise ValueError('CLFG pilot window falls outside DEM bounds')
        row, col = src.index(east, north)
        native = src.read(1, window=Window(col, row, 1, 1), masked=True)[0, 0]
        if np.ma.is_masked(native) or not np.isfinite(native):
            raise ValueError('Missing native DEM elevation at CLFG')
        elevations = {'2m': float(native)}
        coverage = {}
        for metres in (20, 100):
            n = 6000 // metres
            grid = src.read(1, window=win, out_shape=(n, n), masked=True,
                            resampling=Resampling.average)
            row, col = rowcol(rasterio.transform.from_bounds(*bounds, n, n), east, north)
            valid = ~np.ma.getmaskarray(grid) & np.isfinite(grid.data)
            if not valid[row, col]:
                raise ValueError(f'Missing DEM elevation at CLFG at {metres} m')
            key = f'{metres}m'
            elevations[key] = float(grid[row, col])
            coverage[key] = {'cells': grid.size, 'valid_cells': int(valid.sum())}
    return bounds, elevations, coverage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hrrr', type=Path, default=HRRR)
    parser.add_argument('--dem', type=Path, default=DEM)
    parser.add_argument('--start', default='2026-05-22T00:00')
    parser.add_argument('--end', default='2026-05-28T23:00')
    parser.add_argument('--output', type=Path, default=Path(__file__).parent / 'outputs')
    args = parser.parse_args()

    info = dict(line.split(': ', 1) for line in
                (ROOT / 'sites/clfg/site_info.txt').read_text().splitlines())
    lat, lon = (float(info[key].split('(')[-1].rstrip(')')) for key in ('Latitude', 'Longitude'))
    east, north = Transformer.from_crs(4326, 32608, always_xy=True).transform(lon, lat)
    bounds, elevations, coverage = terrain(args.dem, east, north)
    with xr.open_dataset(args.hrrr) as ds:
        if CRS.from_wkt(ds.spatial_ref.attrs['crs_wkt']).to_epsg() != 32608:
            raise ValueError('Expected HRRR grid in EPSG:32608')
        for name, unit in zip(VARIABLES, UNITS):
            if ds[name].attrs.get('units') != unit:
                raise ValueError(f'Unexpected units for {name}')
        indices = {}
        for dim, coordinate in [('x', east), ('y', north)]:
            order = np.argsort(ds[dim].values)
            indices[dim] = order[cell_index(ds[dim].values[order], coordinate)]
        point = ds[VARIABLES].isel(**indices).sel(time=slice(args.start, args.end)).load()
    expected = pd.date_range(args.start, args.end, freq='h', name='time')
    if (expected.empty or not point.indexes['time'].equals(expected)
            or ('valid_time' in point and not np.array_equal(point.valid_time, point.time))):
        raise ValueError('Expected complete hourly UTC coverage with matching valid times')
    frame = point.to_dataframe()[VARIABLES]
    if not np.isfinite(frame.to_numpy()).all():
        raise ValueError('Missing HRRR-AK values in the pilot window')
    summary = dict(latitude=lat, longitude=lon, east_m=east, north_m=north,
                   hrrrak_source=str(args.hrrr), dem_source=str(args.dem),
                   hrrrak_cell_x_m=float(point.x), hrrrak_cell_y_m=float(point.y),
                   bounds_utm8n_m=bounds, coverage=coverage, start_utc=args.start,
                   end_utc=args.end, hours=len(frame), lapse_rate_K_per_m=LAPSE_RATE,
                   hrrrak_orography_min_m=float(frame.orog.min()),
                   hrrrak_orography_max_m=float(frame.orog.max()), terrain={})
    for resolution, elevation in elevations.items():
        delta = elevation - frame.orog
        correction = -LAPSE_RATE * delta
        frame[f'temp_lapse_{resolution}_K'] = frame.temp + correction
        summary['terrain'][resolution] = dict(elevation_m=elevation,
                                              mean_elevation_difference_m=float(delta.mean()),
                                              mean_temperature_change_K=float(correction.mean()))
    args.output.mkdir(parents=True, exist_ok=True)
    frame.rename_axis('time_utc').to_csv(args.output / 'clfg_baseline.csv')
    (args.output / 'clfg_baseline.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
