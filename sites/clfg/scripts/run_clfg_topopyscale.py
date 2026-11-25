"""Extract the nearest CLFG forcing cells and run matched WY2026 SNOWPACK cases."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd
import xarray as xr

from run_clfg import MODEL_ROOT, read_smet, run_model

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'downscaling'))
from icefield_comparison import RESOLUTIONS, RUN, site

EXPECTED = pd.date_range('2025-10-01', periods=8760, freq='h')
BASE = 'hrrrak_clfg_WY2026'
FIELDS = ['TA', 'RH', 'VW', 'DW', 'ISWR', 'ILWR', 'PSUM', 'PS']


def prepare(resolution, site_dir, forcing_root):
    name = f'topopyscale_{resolution}m'
    station = f'{name}_clfg_WY2026'
    source = forcing_root / f'{resolution}m'
    baseline = site_dir / 'input/hrrrak_WY2026' / BASE
    _, _, x, y, altitude = site()
    with xr.open_dataset(source / 'terrain.nc') as terrain:
        dx = terrain.cell_x.values - x
        dy = terrain.cell_y.values - y
        cell = int(np.argmin(np.hypot(dx, dy)))
        (row, col), = np.argwhere(terrain.cell_id.values == cell)
        row, col = int(row), int(col)
        grid_z = float(terrain.elevation.isel(y=row, x=col))
    with xr.open_dataset(source / 'forcing.nc') as forcing:
        ds = forcing.isel(cell=cell).load()
    if not ds.indexes['time'].equals(EXPECTED):
        raise ValueError(f'Expected 8,760 complete WY2026 hours in {source}')
    u, v = ds.u.values, ds.v.values
    frame = pd.DataFrame(dict(
        TA=ds.t.values, RH=ds.rh.values / 100, VW=np.hypot(u, v),
        DW=np.rad2deg(np.arctan2(-u, -v)) % 360,
        ISWR=ds.SW.values, ILWR=ds.LW.values, PSUM=ds.tp.values, PS=ds.p.values),
        index=EXPECTED)[FIELDS]
    if (not np.isfinite(frame).all().all() or not frame.RH.between(0, 1).all()
            or (frame[['ISWR', 'ILWR', 'PSUM', 'PS']] < 0).any().any()):
        raise ValueError(f'Invalid forcing in {source}')

    target = site_dir / 'input' / f'{name}_WY2026'
    output = site_dir / 'output' / f'{station}_heatflux_soiltemp_zero.smet'
    ini = site_dir / 'config' / f'{station}.ini'
    log = site_dir / 'logs' / f'{station}.log'
    if any(p.exists() for p in (target, output, ini, log)):
        raise FileExistsError(f'Inputs or outputs already exist for {station}')
    target.mkdir()
    stem = target / station
    header, _ = read_smet(baseline.with_suffix('.smet'), ['timestamp'])
    replacements = {
        'station_id': station, 'station_name': f'CLFG TopoPyScale {resolution} m',
        'source': f'TopoPyScale {resolution} m nearest CLFG cell {cell}; no extra lapse rate',
    }
    header.update(replacements)
    with stem.with_suffix('.smet').open('x') as out:
        out.write('SMET 1.1 ASCII\n[HEADER]\n')
        for key, value in header.items():
            out.write(f'{key:20} = {value}\n')
        out.write('[DATA]\n')
        frame.to_csv(out, sep=' ', header=False, date_format='%Y-%m-%dT%H:%M',
                     float_format='%.6f')
    sno = baseline.with_suffix('.sno').read_text()
    for key, value in replacements.items():
        sno = re.sub(rf'(?m)^{key}\s*=.*$', f'{key:20} = {value}', sno)
    stem.with_suffix('.sno').write_text(sno)
    config = (site_dir / 'config' / f'{BASE}.ini').read_text()
    config = config.replace(BASE, station).replace('../input/hrrrak_WY2026',
                                                  f'../input/{target.name}')
    ini.write_text(config)
    summary = dict(resolution_m=resolution, cell_id=cell, row=row, col=col,
                   site_elevation_m=altitude, forcing_elevation_m=grid_z,
                   cell_minus_site_m=grid_z-altitude,
                   distance_to_center_m=float(np.hypot(dx[cell], dy[cell])),
                   temperature_lapse_adjustment_K=0.0,
                   profile_fallback_hours=int(ds.profile_fallback.sum()),
                   source=str(source / 'forcing.nc'))
    stem.with_suffix('.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(f'{station}: cell {cell}, grid elevation {grid_z:.2f} m', flush=True)
    return station


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site-dir', type=Path,
                        default=Path(os.environ.get('CLFG_MODEL_SITE', MODEL_ROOT / 'clfg')))
    parser.add_argument('--forcing-root', type=Path, default=RUN / 'WY2026')
    parser.add_argument('--resolutions', nargs='+', type=int, choices=RESOLUTIONS,
                        default=RESOLUTIONS)
    parser.add_argument('--guard', nargs='*', type=int, choices=RESOLUTIONS, default=(),
                        help='Use the existing build-specific empty-column guard for selected runs.')
    parser.add_argument('--run-prepared', action='store_true',
                        help='Run already prepared inputs in a clean output directory.')
    args = parser.parse_args()
    root = args.site_dir.resolve()
    jobs = {m: (f'topopyscale_{m}m_clfg_WY2026' if args.run_prepared
                else prepare(m, root, args.forcing_root)) for m in args.resolutions}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {m: pool.submit(run_model, station, root, EXPECTED, guard=m in args.guard)
                   for m, station in jobs.items()}
        for m, task in futures.items():
            print(f'{m} m: {task.result():,} verified hourly snow depth and SWE values', flush=True)


if __name__ == '__main__':
    main()
