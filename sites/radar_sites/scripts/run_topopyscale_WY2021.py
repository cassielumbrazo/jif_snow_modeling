"""Run WY2021 radar-site SNOWPACK with a common raw HRRR-AK spin-up."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from shutil import which
import subprocess
import sys

import numpy as np
import pandas as pd
import xarray as xr

from prepare_radar_site_forcing import FIELDS, MODEL_ROOT, PERIOD, read_smet
from run_radar_sites import with_empty_column_guard

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'downscaling'))
from radar_icefield_comparison import RESOLUTIONS, RUN, SITES, geometry, radar_sites

WY2021 = pd.date_range('2020-10-01T00:00', '2021-09-30T23:00', freq='h')
RUN_HOURS = pd.date_range('2019-10-01T05:00', WY2021[-1], freq='h')
SPINUP = RUN_HOURS[RUN_HOURS < WY2021[0]]
EXPERIMENT = 'heatflux_soiltemp_zero'


def prepare(model_root, cells, site, resolution):
    source = model_root / site.lower()
    original = f'hrrrak_{site.lower()}_{PERIOD}'
    base = source / 'input' / f'hrrrak_{PERIOD}' / original
    station = f'topopyscale_{resolution}m_{site.lower()}_WY2021'
    directory = source / 'input' / f'topopyscale_{resolution}m_WY2021'
    config_path = source / 'config' / f'{station}.ini'
    output_path = source / 'output' / f'{station}_{EXPERIMENT}.smet'
    log = source / 'logs' / f'{station}.log'
    if any(p.exists() for p in (directory, config_path, output_path, log)):
        raise FileExistsError(f'Existing files for {station}')
    header, raw = read_smet(base.with_suffix('.smet'))
    spinup = raw.reindex(SPINUP)[FIELDS]
    if not np.isfinite(spinup.to_numpy()).all():
        raise ValueError(f'Incomplete raw spin-up at {site}')
    row, = cells[(cells.site == site) & (cells.grid == f'TopoPyScale {resolution} m')].itertuples()
    if row.cell_id < 0 or not row.forcing_cell_available:
        raise ValueError(f'No {resolution} m forcing cell at {site}')
    cell = int(row.cell_id)
    input_path = RUN / f'{resolution}m' / 'forcing.nc'
    with xr.open_dataset(input_path) as forcing:
        met = forcing.isel(cell=cell).load()
    if not met.indexes['time'].equals(WY2021):
        raise ValueError(f'Incomplete WY2021 forcing at {site} and {resolution} m')
    u, v = met.u.values, met.v.values
    downscaled = pd.DataFrame(dict(
        TA=met.t.values, RH=met.rh.values / 100, VW=np.hypot(u, v),
        DW=np.rad2deg(np.arctan2(-u, -v)) % 360,
        ISWR=met.SW.values, ILWR=met.LW.values, PSUM=met.tp.values, PS=met.p.values),
        index=WY2021)[FIELDS]
    if (not np.isfinite(downscaled.to_numpy()).all() or not downscaled.RH.between(0, 1).all()
            or (downscaled[['ISWR', 'ILWR', 'PSUM', 'PS']] < 0).any().any()):
        raise ValueError(f'Invalid forcing at {site} and {resolution} m')

    directory.mkdir()
    target = directory / station
    header.update(station_id=station, station_name=f'{site} TopoPyScale {resolution} m',
                  source=f'Raw HRRR-AK spin-up through WY2020; TopoPyScale cell {cell} in WY2021')
    with target.with_suffix('.smet').open('x') as stream:
        stream.write('SMET 1.1 ASCII\n[HEADER]\n')
        for key, value in header.items():
            stream.write(f'{key:20} = {value}\n')
        stream.write('[DATA]\n')
        pd.concat([spinup, downscaled]).to_csv(
            stream, sep=' ', header=False, date_format='%Y-%m-%dT%H:%M', float_format='%.6f')
    sno = base.with_suffix('.sno').read_text().replace(original, station)
    target.with_suffix('.sno').write_text(sno)
    config = (source / 'config' / f'{original}.ini').read_text()
    config = config.replace(original, station).replace(f'../input/hrrrak_{PERIOD}', f'../input/{directory.name}')
    config_path.write_text(config)
    target.with_suffix('.json').write_text(json.dumps(dict(
        site=site, resolution_m=resolution, cell_id=cell, row=int(row.row), col=int(row.col),
        site_elevation_m=row.site_elevation_m, forcing_elevation_m=row.grid_elevation_m,
        cell_minus_site_m=row.grid_minus_site_m, source=str(input_path),
        profile_fallback_hours=int(met.profile_fallback.sum()), spinup_hours=len(SPINUP),
        forcing_start_UTC=str(WY2021[0]), forcing_end_UTC=str(WY2021[-1])), indent=2) + '\n')
    print(f'Prepared {station}, cell {cell}', flush=True)


def run_case(model_root, site, resolution):
    source = model_root / site.lower()
    station = f'topopyscale_{resolution}m_{site.lower()}_WY2021'
    log = source / 'logs' / f'{station}.log'
    command = ['snowpack', '-c', f'{station}.ini',
               '-b', RUN_HOURS[0].isoformat(timespec='minutes'),
               '-e', RUN_HOURS[-1].isoformat(timespec='minutes')]
    if site in {'TKG4', 'DG1'}:
        command, _ = with_empty_column_guard(command)
    with log.open('x') as stream:
        subprocess.run(command, cwd=source / 'config', stdout=stream,
                       stderr=subprocess.STDOUT, check=True)
    if 'FINISHED running' not in log.read_text():
        raise RuntimeError(f'SNOWPACK did not finish. Review {log}')
    _, result = read_smet(source / 'output' / f'{station}_{EXPERIMENT}.smet',
                          ['timestamp', 'HS_mod', 'SWE'])
    if not result.index.equals(RUN_HOURS) or not np.isfinite(result.to_numpy()).all():
        raise ValueError(f'Incomplete output for {station}')
    original = source / 'output' / f'hrrrak_{site.lower()}_{PERIOD}_{EXPERIMENT}.smet'
    _, raw = read_smet(original, ['timestamp', 'HS_mod', 'SWE'])
    pd.testing.assert_frame_equal(result.loc[SPINUP], raw.loc[SPINUP])
    print(f'{station}: identical raw spin-up and {len(WY2021):,} verified WY2021 hours', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-root', type=Path, default=MODEL_ROOT)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    if which('snowpack') is None:
        parser.error('snowpack is required on PATH')
    _, cells = geometry(radar_sites())
    jobs = [(args.model_root, site, m) for site in SITES for m in RESOLUTIONS]
    for job in jobs:
        prepare(job[0], cells, *job[1:])
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for future in [pool.submit(run_case, *job) for job in jobs]:
            future.result()


if __name__ == '__main__':
    main()
