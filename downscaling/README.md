# Juneau Icefield forcing downscaling

Start with CLFG and an hourly pilot from May 22 through May 28, 2026 (UTC).
The window spans the May 25 field visit and has complete local HRRR-AK
coverage. The field record gives approximately 2 m of snow depth and can be
used for a later snow model comparison. The site has no meteorological
observations in the current records.

## CLFG baseline

Run from the Juneau Icefield repo.

```bash
conda run -n jif_snow_modeling python downscaling/clfg_baseline.py
```

The script writes the raw HRRR-AK series and lapse-rate temperature series to
`outputs/clfg_baseline.csv` and the input paths, coverage, and site statistics
to `outputs/clfg_baseline.json`, both relative to this directory. Raw
column units follow the source NetCDF. The `temp_lapse_*_K` columns use the
existing CLFG lapse rate of 6 K/km.

| Terrain source | CLFG elevation | Temperature change from raw HRRR-AK |
| --- | ---: | ---: |
| Containing HRRR-AK cell | 1,030.0 m | — |
| 2 m ArcticDEM site pixel | 652.0 m | +2.268 K |
| 20 m average | 652.8 m | +2.263 K |
| 100 m average | 651.7 m | +2.270 K |

The 20 m and 100 m cells are nested and averaged from the same UTM 8N ArcticDEM
VRT over a 6 × 6 km window. All output cells had valid elevation. The
temperature corrections span less than 0.01 K at CLFG. This measures the
effect of averaging on site elevation and the fixed-lapse-rate baseline.
Slope, aspect, terrain shading, sky-view factor, and differences in the
downscaled forcing remain to be tested.

## TopoPyScale pilot results

All 168 pressure GRIBs for May 22–28 UTC are in
`/hdd/snow_hydrology/hrrrak/icefield_domain/atms_levels`. The native-grid
NetCDF `hrrrak_pressure_20260522-20260528.nc` contains 15 levels from 650 to
1000 hPa and five variables with complete coverage on the 58 × 31 crop. The
reusable workflow lives in `~/python/models/run_topopyscale/hrrrak`. The
adapter derives specific humidity from temperature, relative humidity, and
pressure, and joins each profile with matching surface data.

TopoPyScale 0.2.2 produced all eight checked forcing variables at both 20 m
and 100 m for all 168 hours. Each run used the same atmospheric inputs,
physical point, and 12 × 12 km DEM bounds for horizon calculations. The
checked files are `outputs/clfg_topopyscale_{20,100}m/outputs/forcing_integration.nc`.
Run the comparison from the Icefield repo.

```bash
conda run -n jif_snow_modeling python downscaling/compare_clfg_pilot.py
```

The resulting `outputs/clfg_topopyscale_integration_comparison.csv` joins
both runs with the raw and fixed-lapse-rate baseline. The mean absolute
20 m versus 100 m temperature difference was 0.013 K. Shortwave differed
by 2.3 W/m² on average and by up to 217.3 W/m² in a single hour
(May 26 at 03 UTC, 73.7 W/m² at 20 m and 291.0 W/m² at 100 m).

The nearest native HRRR column has terrain at approximately 928 m and had
usable pressure levels above and below the CLFG target in zero hours.
At least one column within 12 km provided a usable bracket in all 168 hours
at both target elevations. The stock kernel was run with unmasked pressure
levels to verify integration. The resulting forcing and resolution
differences are diagnostic. The next experiment is to test interpolation
using only above-ground levels, check which nearby columns support each
hour, and then repeat the forcing comparison before extending to WY2026.

## WY2026 CLFG resolution test

The detached campaign writes to
`/home/cassie/python/models/run_topopyscale/icefield_domain/clfg_test`.
It compares 1,000, 500, 250, 100, 50, and 20 m over the same 6 × 6 km window. Terrain
horizons use a 3 km buffer on each side. Both notebooks use completed
products as they become available.

- `icefield_clfg_maps.ipynb` maps terrain, the containing CLFG grid cells, and
  an hourly temperature snapshot. It exports `clfg_resolution_test_elevations_WY2026.csv`.
- `icefield_clfg_timeseries.ipynb` plots CLFG forcing and hourly differences
  against the finest completed grid. It exports `clfg_resolution_test_forcing_WY2026.csv`.

Use the **JIF snow modeling** kernel for the NetCDF4 outputs. The elevation
reference is the 2 m ArcticDEM sample at CLFG. The earlier Icefield-wide
500/1,000 m campaign was stopped. Its completed native surface
file is shared with the CLFG runs. See `campaign.log` and
`resource_report.txt` in the CLFG run folder for progress and measured costs.

## WY2021 radar-site comparisons

Use the **JIF snow modeling** kernel to open
[radar-site maps](icefield_WY2021_radar_maps.ipynb) and
[radar-site time series](icefield_WY2021_radar_timeseries.ipynb).
They use the established SNOWPACK points for TKG2, TKG3, C161, TKG4, and DG1,
with native HRRR-AK and the 1,000 m and 500 m terrain and forcing outputs.
The notebooks read each validated product as it appears under
`~/python/models/run_topopyscale/icefield_domain/WY2021`.

Both notebooks end with a site-versus-grid elevation table and save
`outputs/radar_sites_grid_elevations_WY2021.csv`. The time-series notebook
also saves `outputs/radar_sites_forcing_WY2021.csv` with hourly values.
