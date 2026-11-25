"""Read WY2021 Icefield forcing at the established SNOWPACK radar sites."""
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Proj, Transformer
import xarray as xr

from icefield_comparison import ALASKA_GRID, edges, index, raw_geometry, raw_path

YEAR = 2021
RESOLUTIONS = (1000, 500)
NATIVE = 'Native HRRR-AK'
RUN = Path(os.environ.get(
    'JIF_RADAR_ICEFIELD_RUN', '/home/cassie/python/models/run_topopyscale/icefield_domain/WY2021'))
MODEL = Path('/home/cassie/python/models/run_snowpack/sites')
SITES = ('TKG2', 'TKG3', 'C161', 'TKG4', 'DG1')
SURFACE = RUN / 'surface_native.nc'


def radar_sites():
    """Use the exact configured coordinates and elevations, including TKG4."""
    transform = Transformer.from_crs(4326, 32608, always_xy=True)
    records = []
    for site in SITES:
        name = site.lower()
        path = MODEL / name / 'input/hrrrak_WY2020-WY2026' / f'hrrrak_{name}_WY2020-WY2026.json'
        meta = json.loads(path.read_text())
        lon, lat = meta['longitude'], meta['latitude']
        x, y = transform.transform(lon, lat)
        records.append(dict(site=site, longitude=lon, latitude=lat, x=x, y=y,
                            site_elevation_m=meta['elevation_m'],
                            coordinate_source=meta['coordinate_source']))
    return pd.DataFrame(records).set_index('site')


def geometry(sites):
    """Return grid edges and containing site-cell lookup, including source elevations."""
    layouts = {}
    rows = []
    raw = SURFACE if SURFACE.is_file() else raw_path(YEAR)
    to_model = Transformer.from_crs(4326, ALASKA_GRID, always_xy=True)
    to_utm = Transformer.from_crs(ALASKA_GRID, 32608, always_xy=True)
    with xr.open_dataset(raw) as ds:
        ds = ds.sel(time=slice('2020-10-01', '2021-09-30'))
        x, y = raw_geometry(ds)
        grid_x, grid_y = to_utm.transform(*np.meshgrid(edges(x), edges(y)))
        layouts[NATIVE] = (grid_x, grid_y, ds.orog.isel(time=0).values)
        for site, row in sites.iterrows():
            sx, sy = to_model.transform(row.longitude, row.latitude)
            i, j = index(y, sy), index(x, sx)
            values = ds.orog.isel(y=i, x=j).values
            rows.append(site_cell(site, row, NATIVE, i, j, None, values))
    for m in RESOLUTIONS:
        track = RUN / f'{m}m/terrain.nc'
        if not track.is_file():
            continue
        label = f'TopoPyScale {m} m'
        with xr.open_dataset(track) as ds:
            x, y = ds.x.values, ds.y.values
            grid_x, grid_y = np.meshgrid(edges(x), edges(y))
            layouts[label] = (grid_x, grid_y, ds.elevation.values)
            for site, row in sites.iterrows():
                i, j = index(y, row.y), index(x, row.x)
                cell = int(ds.cell_id.isel(y=i, x=j))
                z = float(ds.elevation.isel(y=i, x=j))
                rows.append(site_cell(site, row, label, i, j, cell, [z]))
    return layouts, pd.DataFrame(rows)


def site_cell(site, point, label, row, col, cell, values):
    samples = np.asarray(values, dtype=float)
    if not np.isfinite(samples).any():
        z = low = high = np.nan
    else:
        z, low, high = np.nanmedian(samples), np.nanmin(samples), np.nanmax(samples)
    return dict(site=site, grid=label, row=row, col=col, cell_id=cell,
                site_elevation_m=point.site_elevation_m, grid_elevation_m=z,
                grid_elevation_min_m=low, grid_elevation_max_m=high,
                grid_minus_site_m=z-point.site_elevation_m,
                forcing_cell_available=cell is None or cell >= 0)


def elevation_table(cells, output):
    """Save the full comparison and show a concise site-by-grid table."""
    output.mkdir(exist_ok=True)
    cells.to_csv(output / 'radar_sites_grid_elevations_WY2021.csv', index=False)
    result = cells.groupby('site', sort=False).site_elevation_m.first().to_frame('Site elevation (m)')
    for label, grid in cells.groupby('grid', sort=False):
        grid = grid.set_index('site')
        result[f'{label} elevation (m)'] = grid.grid_elevation_m
        result[f'{label} Δ (m)'] = grid.grid_minus_site_m
        if label == NATIVE:
            result['Native min–max (m)'] = [
                f'{row.grid_elevation_min_m:.1f}–{row.grid_elevation_max_m:.1f}'
                for row in grid.reindex(result.index).itertuples()
            ]
    return result.round(1)


def load_forcing(site, cells):
    """Read one containing cell per available output, preserving hourly UTC."""
    if not SURFACE.is_file():
        return {}
    match = cells[cells.site == site].set_index('grid')
    row = match.loc[NATIVE]
    with xr.open_dataset(SURFACE) as ds:
        raw = ds.isel(y=int(row.row), x=int(row.col)).load()
    lon = (float(raw.longitude) + 180) % 360 - 180
    gamma = np.deg2rad(Proj(ALASKA_GRID).get_factors(lon, float(raw.latitude)).meridian_convergence)
    u, v = raw['10u'].values, raw['10v'].values
    u_east, v_north = u*np.cos(gamma)+v*np.sin(gamma), -u*np.sin(gamma)+v*np.cos(gamma)
    frames = {NATIVE: forcing_frame(raw, raw.temp, raw.rh, raw.pressure,
                                     u_east, v_north, raw.swrad, raw.lwrad, raw.precip)}
    for m in RESOLUTIONS:
        label = f'TopoPyScale {m} m'
        path = RUN / f'{m}m/forcing.nc'
        if label not in match.index or not path.is_file() or not match.loc[label, 'forcing_cell_available']:
            continue
        cell = int(match.loc[label, 'cell_id'])
        with xr.open_dataset(path) as ds:
            forcing = ds.isel(cell=cell).load()
        if not forcing.indexes['time'].equals(raw.indexes['time']):
            raise ValueError(f'Forecast valid times differ for {label} at {site}')
        frames[label] = forcing_frame(forcing, forcing.t, forcing.rh, forcing.p, forcing.u,
                                      forcing.v, forcing.SW, forcing.LW, forcing.tp)
        frames[label]['fallback_percent'] = 100 * forcing.profile_fallback.values.astype(float)
    return frames


def forcing_frame(ds, t, rh, pressure, u, v, sw, lw, tp):
    return pd.DataFrame({
        'temperature_C': np.asarray(t) - 273.15, 'rh_percent': np.asarray(rh),
        'pressure_hPa': np.asarray(pressure) / 100, 'wind_m_s': np.hypot(u, v),
        'u_east_m_s': np.asarray(u), 'v_north_m_s': np.asarray(v),
        'shortwave_W_m2': np.asarray(sw), 'longwave_W_m2': np.asarray(lw),
        'precip_mm': np.asarray(tp),
    }, index=ds.indexes['time'])
