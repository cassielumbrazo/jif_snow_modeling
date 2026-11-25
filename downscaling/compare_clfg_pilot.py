"""Compare the CLFG integration outputs with the raw and lapse-rate baselines."""
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

OUTPUT = Path(__file__).resolve().parent / 'outputs'
FIELDS = {'t': 'temperature_K', 'q': 'specific_humidity_kg_kg',
          'p': 'pressure_Pa', 'ws': 'wind_speed_m_s', 'wd': 'wind_direction_deg',
          'SW': 'shortwave_W_m2', 'LW': 'longwave_W_m2', 'tp': 'precip_mm_h'}


def main():
    frame = pd.read_csv(OUTPUT / 'clfg_baseline.csv', parse_dates=['time_utc'],
                        index_col='time_utc')
    for resolution in (20, 100):
        path = OUTPUT / f'clfg_topopyscale_{resolution}m/outputs/forcing_integration.nc'
        with xr.open_dataset(path) as ds:
            if not ds.indexes['time'].equals(frame.index):
                raise ValueError(f'Timestamps in {path} differ from the baseline')
            for variable, label in FIELDS.items():
                values = ds[variable].transpose('time', ...).values.reshape(len(frame))
                if variable == 'wd':
                    values = np.rad2deg(values) % 360
                frame[f'topopyscale_{resolution}m_{label}'] = values
    frame.to_csv(OUTPUT / 'clfg_topopyscale_integration_comparison.csv')
    for label in ('temperature_K', 'shortwave_W_m2', 'longwave_W_m2'):
        delta = frame[f'topopyscale_20m_{label}'] - frame[f'topopyscale_100m_{label}']
        print(f'{label} 20 m − 100 m mean absolute difference {delta.abs().mean():.3f}, '
              f'maximum {delta.abs().max():.3f}')


if __name__ == '__main__':
    main()
