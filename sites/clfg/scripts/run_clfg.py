"""Prepare and run paired HRRR-AK simulations at CLFG through WY2026."""

import argparse
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
from pyproj import Transformer
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'radar_sites/scripts'))
from prepare_radar_site_forcing import HRRR, MODEL_ROOT, prepare_point, read_smet
from run_radar_sites import with_empty_column_guard

SITE = 'clfg'
FORCINGS = ('hrrrak', 'hrrrak_lapserate')
DEM = Path('/hdd/snow_hydrology/DEMs/ArcticDEM_edits/icefield_domain/jif_mosaic/jif_tiles_utm8n_2m.vrt')


def run_model(station, site_dir, expected, *, guard=False):
    output = site_dir / 'output' / f'{station}_heatflux_soiltemp_zero.smet'
    logfile = site_dir / 'logs' / f'{station}.log'
    command = ['snowpack', '-c', f'{station}.ini',
               '-b', expected[0].strftime('%Y-%m-%dT%H:%M'),
               '-e', expected[-1].strftime('%Y-%m-%dT%H:%M')]
    if guard:
        command, _ = with_empty_column_guard(command)
    with logfile.open('x') as log:
        subprocess.run(command, cwd=site_dir / 'config', stdout=log, stderr=subprocess.STDOUT, check=True)
    if 'FINISHED running' not in logfile.read_text():
        raise RuntimeError(f'SNOWPACK did not finish. Review {logfile}')
    _, frame = read_smet(output, ['timestamp', 'HS_mod', 'SWE'])
    if not frame.index.equals(expected) or not np.isfinite(frame.to_numpy()).all():
        raise ValueError(f'Incomplete snow depth or SWE output: {output}')
    return len(frame)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, default=MODEL_ROOT)
    parser.add_argument('--start-water-year', type=int, choices=range(2020, 2027), default=2026)
    parser.add_argument('--end-water-year', type=int, choices=range(2020, 2027), default=2026)
    parser.add_argument('--lapse-rate', type=Decimal,
                        help='Run only the sensitivity case at this rate in °C per 100 m.')
    parser.add_argument('--empty-column-guard', nargs='+', choices=FORCINGS, default=(),
                        help='Use the build-specific radar-site guard for the selected runs.')
    args = parser.parse_args()
    first_year, last_year = args.start_water_year, args.end_water_year
    if first_year > last_year:
        parser.error('the start water year must precede or equal the end water year')
    if args.lapse_rate is not None and (not args.lapse_rate.is_finite() or args.lapse_rate < 0):
        parser.error('the lapse rate must be finite and nonnegative')
    period = f'WY{first_year}' if first_year == last_year else f'WY{first_year}-WY{last_year}'
    corrected_name = 'hrrrak_lapserate'
    if args.lapse_rate is not None:
        rate = format(args.lapse_rate.normalize(), 'f').replace('.', 'p')
        corrected_name = f'{corrected_name}_{rate}'
    forcings = FORCINGS if args.lapse_rate is None else (corrected_name,)
    site_dir = args.output_root.resolve() / SITE
    for forcing in forcings:
        station = f'{forcing}_{SITE}_{period}'
        if ((site_dir / 'input' / f'{forcing}_{period}').exists()
                or (site_dir / 'config' / f'{station}.ini').exists()
                or (site_dir / 'logs' / f'{station}.log').exists()
                or any((site_dir / 'output').glob(f'{station}_*'))):
            raise FileExistsError(f'{station} already exists in {site_dir}. Use another --output-root.')

    site_info = Path(__file__).resolve().parents[1] / 'site_info.txt'
    info = dict(line.split(': ', 1) for line in site_info.read_text().splitlines())
    lat, lon = (float(info[key].split('(')[-1].rstrip(')')) for key in ('Latitude', 'Longitude'))
    east, north = Transformer.from_crs(4326, 32608, always_xy=True).transform(lon, lat)
    with rasterio.open(DEM) as dem:
        if dem.crs.to_epsg() != 32608:
            raise ValueError('Expected ArcticDEM in UTM zone 8N')
        sample = next(dem.sample([(east, north)], masked=True))[0]
        if np.ma.is_masked(sample) or not np.isfinite(sample):
            raise ValueError('The ArcticDEM has no valid elevation at CLFG')
    summary, raw, _ = prepare_point(
        SITE, site_dir.parent, HRRR,
        {'coordinate_source': 'User-supplied WGS 84 coordinates', 'elevation_source': str(DEM)},
        east=east, north=north, elevation=float(sample), lat=lat, lon=lon,
        period=period, start=f'{first_year - 1}-10-01T00:00', end=f'{last_year}-09-30T23:00',
        lapse_rate=0.006 if args.lapse_rate is None else float(args.lapse_rate / 100),
        corrected_name=corrected_name, include_raw=args.lapse_rate is None,
    )
    print(json.dumps(summary, indent=2), flush=True)
    (site_dir / 'logs').mkdir(exist_ok=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = {
            forcing: pool.submit(run_model, f'{forcing}_{SITE}_{period}', site_dir, raw.index,
                                 guard=(forcing if forcing in FORCINGS else 'hrrrak_lapserate') in args.empty_column_guard)
            for forcing in forcings
        }
        for forcing, job in jobs.items():
            print(f'{forcing}: {job.result():,} verified hourly outputs', flush=True)


if __name__ == '__main__':
    main()
