"""Prepare paired raw and temperature-corrected HRRR-AK point inputs."""
from pathlib import Path
import argparse
import configparser
import json
import re
import shlex
import sys

import numpy as np
import pandas as pd
from pyproj import CRS, Transformer
import xarray as xr

HRRR = Path('/hdd/snow_hydrology/hrrrak/icefield_domain/netcdf/hrrrak_f567_WY2020-WY2026_utm.nc')
PITS = Path('/hdd/snow_hydrology/JIF_radar/jif_snow_pit_sites_2021.csv')
MODEL_ROOT = Path('/home/cassie/python/models/run_snowpack/sites')
TEMPLATES = Path(__file__).resolve().parent / 'templates'
TEMPLATE = TEMPLATES / 'empty_profile.sno'
PERIOD = 'WY2020-WY2026'
SITES = ('tkg2', 'tkg3', 'c161', 'tkg4', 'dg1')
FIELDS = ['TA', 'RH', 'VW', 'DW', 'ISWR', 'ILWR', 'PSUM', 'PS']
VARIABLES = ['temp', 'rh', '10u', '10v', 'swrad', 'lwrad', 'precip_rate', 'pressure', 'orog']
UNITS = ['K', '%', 'm s**-1', 'm s**-1', 'W m**-2', 'W m**-2', 'kg m**-2 s**-1', 'Pa', 'm']


def cell_index(values, coordinate):
    """Containing stored UTM cell; exact edge ties go east/north."""
    values = np.asarray(values)
    edges = np.r_[values[0] - (values[1]-values[0])/2,
                  (values[:-1]+values[1:])/2,
                  values[-1] + (values[-1]-values[-2])/2]
    i = int(np.searchsorted(edges, coordinate, side='right')-1)
    if not 0 <= i < len(values):
        raise ValueError('Pit is outside the HRRR grid')
    return i


def read_smet(path, columns=None):
    """Read stored values and retain their header unit metadata."""
    header = {}
    with Path(path).open() as f:
        for line in f:
            if line.strip() == '[DATA]':
                break
            if '=' in line:
                k, v = line.split('=', 1)
                header[k.strip()] = v.strip()
        else:
            raise ValueError(f'No SMET data section: {path}')
        frame = pd.read_csv(f, sep=r'\s+', names=header['fields'].split(), usecols=columns)
    frame.index = pd.DatetimeIndex(pd.to_datetime(frame.pop('timestamp')))
    frame.index -= pd.Timedelta(hours=float(header['tz']))
    if not frame.index.is_unique or not frame.index.is_monotonic_increasing:
        raise ValueError(f'Invalid timestamps: {path}')
    return header, frame.replace(float(header['nodata']), np.nan)


def load_prepared(site, output_root=MODEL_ROOT):
    """Inspect the existing paired forcing without modifying model inputs."""
    site = site.lower()
    frames = {}
    metadata = []
    for forcing in ['hrrrak', 'hrrrak_lapserate']:
        stem = Path(output_root)/site/'input'/f'{forcing}_{PERIOD}'/f'{forcing}_{site}_{PERIOD}'
        _, frames[forcing] = read_smet(stem.with_suffix('.smet'))
        metadata.append(json.loads(stem.with_suffix('.json').read_text()))
        if not (Path(output_root)/site/'config'/f'{stem.name}.ini').is_file():
            raise FileNotFoundError(f'Missing configuration for {stem.name}')
    if metadata[0] != metadata[1]:
        raise ValueError('Paired forcing metadata disagree')
    pd.testing.assert_frame_equal(frames['hrrrak'].drop(columns='TA'), frames['hrrrak_lapserate'].drop(columns='TA'))
    return metadata[0], frames['hrrrak'], frames['hrrrak_lapserate']


def prepare(site, output_root=MODEL_ROOT, hrrr=HRRR, pits=PITS, lapse_rate=0.006):
    site = site.lower()
    if site not in SITES:
        raise ValueError('Choose tkg2, tkg3, c161, tkg4, or dg1')
    products = []
    for forcing in ['hrrrak', 'hrrrak_lapserate']:
        stem = Path(output_root)/site/'input'/f'{forcing}_{PERIOD}'/f'{forcing}_{site}_{PERIOD}'
        products.extend(stem.with_suffix(ext) for ext in ['.smet', '.sno', '.json'])
        products.append(Path(output_root)/site/'config'/f'{stem.name}.ini')
    if all(p.is_file() for p in products):
        summary, raw, corrected = load_prepared(site, output_root)
        if (summary['source'] != str(hrrr) or summary['pit_source'] != str(pits)
                or summary['lapse_rate_K_per_m'] != lapse_rate):
            raise ValueError('Existing inputs use different settings; choose another output root to regenerate.')
        return summary, raw, corrected
    if any(p.exists() for p in products):
        raise FileExistsError('Incomplete existing setup; review it or choose another output root.')
    inventory = pd.read_csv(pits).set_index('site_id', verify_integrity=True)
    pit = inventory.loc[site.upper()]
    if 'northing_outside_study_area' in str(pit.quality_flags):
        raise ValueError('Review flagged pit coordinates first')
    east, north, elevation = map(float, (pit.east, pit.north, pit.elevation_m))
    if not np.isfinite([east, north, elevation, lapse_rate]).all() or lapse_rate < 0:
        raise ValueError('Invalid coordinates, elevation, or lapse rate')
    lon, lat = Transformer.from_crs(32608, 4326, always_xy=True).transform(east, north)
    slope = 0.0
    if site == 'tkg4':
        # Preserve the established model point rather than moving to the pit.
        lat, lon, elevation, slope = 58.63447, -134.23708, 1120.0, 38.0
        east, north = Transformer.from_crs(4326, 32608, always_xy=True).transform(lon, lat)
    with xr.open_dataset(hrrr) as ds:
        if CRS.from_wkt(ds.spatial_ref.attrs['crs_wkt']).to_epsg() != 32608:
            raise ValueError('Expected EPSG:32608')
        ds = ds.sortby('x').sortby('y')
        ix, iy = cell_index(ds.x, east), cell_index(ds.y, north)
        for v, unit in zip(VARIABLES, UNITS):
            if ds[v].attrs.get('units') != unit:
                raise ValueError(f'Unexpected {v} units: {ds[v].attrs.get("units")}')
        times = pd.DatetimeIndex(ds.time.values)
        if times.hasnans or not times.is_unique or not times.is_monotonic_increasing or not (times == times.floor('h')).all():
            raise ValueError('Expected unique, increasing hourly UTC timestamps')
        if 'valid_time' in ds and not np.array_equal(ds.valid_time.values, ds.time.values):
            raise ValueError('Resolve time/valid_time mismatch')
        point = ds[VARIABLES].isel(x=ix, y=iy).load()
    frame = point.to_dataframe()[VARIABLES]
    frame.index = times
    expected = pd.date_range(times.min(), times.max(), freq='h')
    frame = frame.reindex(expected)
    raw = pd.DataFrame(index=expected)
    raw['TA'], raw['RH'] = frame.temp, frame.rh / 100
    raw['VW'] = np.hypot(frame['10u'], frame['10v'])
    raw['DW'] = (270 - np.degrees(np.arctan2(frame['10v'], frame['10u']))) % 360
    raw['ISWR'], raw['ILWR'], raw['PS'] = frame.swrad, frame.lwrad, frame.pressure
    raw['PSUM'] = frame.precip_rate * 3600  # rate to mm per hourly interval
    raw = raw[FIELDS].replace([np.inf, -np.inf], np.nan)
    if ((raw.RH.dropna() < 0) | (raw.RH.dropna() > 1)).any() or (raw.PSUM.dropna() < 0).any():
        raise ValueError('Invalid relative humidity or negative precipitation')
    corrected = raw.copy()
    correction = -lapse_rate * (elevation-frame.orog)
    corrected['TA'] += correction
    pd.testing.assert_frame_equal(raw.drop(columns='TA'), corrected.drop(columns='TA'))
    summary = dict(site=site, pit_date=str(pit.pit_date), quality_flags='' if pd.isna(pit.quality_flags) else str(pit.quality_flags),
                   datum='Pit horizontal datum provisionally EPSG:32608; vertical datum unconfirmed',
                   source=str(hrrr), pit_source=str(pits), latitude=lat, longitude=lon, elevation_m=elevation,
                   grid_x_m=float(point.x), grid_y_m=float(point.y),
                   start_UTC=str(expected.min()), end_UTC=str(expected.max()), rows=len(expected),
                   missing_timestamps=[str(t) for t in expected.difference(times)],
                   missing_values=raw.isna().sum().astype(int).to_dict(),
                   hrrr_elevation_min_m=float(frame.orog.min()), hrrr_elevation_max_m=float(frame.orog.max()),
                   lapse_rate_K_per_m=lapse_rate, correction_min_K=float(correction.min()), correction_max_K=float(correction.max()),
                   slope_angle_deg=slope,
                   initialization='Empty profile, SoilAlbedo 0.4, no glacier ice/firn layers; TKG4 substrate parameters',
                   experiment='heatflux_soiltemp_zero',
                   coordinate_source='Existing TKG4 model point' if site == 'tkg4' else '2021 pit inventory')
    template = TEMPLATE.read_text()
    for forcing, data in [('hrrrak', raw), ('hrrrak_lapserate', corrected)]:
        station = f'{forcing}_{site}_{PERIOD}'
        base = Path(output_root)/site
        target = base/'input'/f'{forcing}_{PERIOD}'
        target.mkdir(parents=True, exist_ok=True)
        for directory in ['config', 'output']:
            (base/directory).mkdir(exist_ok=True)
        stem = target/station
        if stem.with_suffix('.smet').exists() or stem.with_suffix('.sno').exists():
            raise FileExistsError(f'Refusing to overwrite inputs: {stem}')
        header = dict(station_id=station, station_name=f'HRRR-AK {site.upper()} {forcing}',
                      latitude=f'{lat:.8f}', longitude=f'{lon:.8f}', easting=east, northing=north,
                      epsg=32608, altitude=elevation, nodata=-999, tz=0,
                      source='HRRR-AK stored UTM cell; hourly temperature-only lapse correction' if forcing.endswith('lapserate') else 'HRRR-AK stored UTM cell; raw forcing')
        with stem.with_suffix('.smet').open('w') as f:
            f.write('SMET 1.1 ASCII\n[HEADER]\n')
            for key, value in header.items():
                f.write(f'{key:20} = {value}\n')
            f.write('fields = timestamp '+' '.join(FIELDS)+'\n[DATA]\n')
            data.to_csv(f, sep=' ', header=False, date_format='%Y-%m-%dT%H:%M', float_format='%.6f', na_rep='-999')
        sno = template
        for key, value in {**header, 'ProfileDate': expected.min().strftime('%Y-%m-%dT%H:%M'), 'SlopeAngle': str(slope), 'SlopeAzi': '0.0'}.items():
            sno = re.sub(rf'(?m)^{key}\s*=.*$', f'{key:20} = {value}', sno)
        stem.with_suffix('.sno').write_text(sno.rstrip()+'\n')
        stem.with_suffix('.json').write_text(json.dumps(summary, indent=2)+'\n')
        config = configparser.ConfigParser(interpolation=None, delimiters=('=',))
        config.optionxform = str
        config.read(TEMPLATES / 'heatflux_soiltemp_zero.ini')
        relative_input = f'../input/{forcing}_{PERIOD}'
        config['Input'].update(METEOPATH=relative_input, STATION1=station+'.smet',
                               SNOW='SMET', SNOWPATH=relative_input,
                               SNOWFILE1=station+'.sno', COLD_START='false')
        config['Output']['METEOPATH'] = '../output'
        config['Output']['EXPERIMENT'] = 'heatflux_soiltemp_zero'
        with (base/'config'/f'{station}.ini').open('w') as f:
            config.write(f)
    run_script = Path(output_root)/site/'run_WY2020-WY2026.sh'
    command = [sys.executable, str(Path(__file__).resolve().with_name('run_radar_sites.py')),
               '--model-root', str(Path(output_root).resolve()), '--sites', site, '--workers', '2']
    run_script.write_text('#!/usr/bin/env bash\nset -euo pipefail\nexec '+shlex.join(command)+'\n')
    run_script.chmod(0o755)
    return summary, raw, corrected


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sites', nargs='+', default=list(SITES))
    parser.add_argument('--output-root', type=Path, default=MODEL_ROOT)
    args = parser.parse_args()
    for site in args.sites:
        summary, _, _ = prepare(site, output_root=args.output_root)
        print(json.dumps(summary, indent=2), flush=True)
