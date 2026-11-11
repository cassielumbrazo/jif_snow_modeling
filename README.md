# Juneau Icefield snow modeling

Point and future distributed snow modeling on the Juneau Icefield, with radar
snow observations for comparison. This working repository starts from the MLD4
and TKG4 workflows in
[snow_modeling_point](https://github.com/cassielumbrazo/snow_modeling_point).

| Folder | Purpose |
| --- | --- |
| `sites/mld4/` | MLD4 forcing preparation and model-output analysis |
| `sites/tkg4/` | TKG4 forcing preparation and model-output analysis |
| `sites/radar_sites/` | Five-site forcing review, model execution, and pit/radar comparison |
| `jif_domain/` | Existing shared HRRR-AK processing, DEM preparation, point extraction, and domain maps |
| `radar/` | Radar data inventory, exploration notebook, and point maps |
| `envs/` | JIF Python environment snapshot and setup instructions |
| `docs/` | Import provenance |

Keep shared radar-site forcing and analysis in `sites/radar_sites/`; its
[combined site notes](sites/radar_sites/site_summary.md) document every radar site.
The older MLD4 and TKG4 work remains in its existing folders. Keep processing shared across sites in `jif_domain/`.
Add a distributed modeling folder when that work begins.

## Radar pit simulations

The five-site workflow is in [`sites/radar_sites/`](sites/radar_sites/):

1. [Review forcing and site elevations](sites/radar_sites/01_review_radar_site_forcing.ipynb):
   reads the existing raw and temperature-corrected forcing, shows a site map,
   and compares temperatures without regenerating inputs.
2. [Compare models, pits, and radar](sites/radar_sites/02_compare_model_pit_radar_WY2021.ipynb):
   loads all ten runs, audits their common coverage, and compares WY2021
   depth/SWE with the archived pit sheets and nearby radar observations. Final
   tables report signed depth differences and mean absolute differences by
   simulation and observation source, with one overall mean absolute difference.

Use the **JIF snow modeling** kernel. The former site-specific forcing notebooks
have been consolidated into the forcing review notebook. Reusable preparation,
run, and comparison scripts live beside these notebooks.

```bash
python sites/radar_sites/prepare_radar_site_forcing.py
python sites/radar_sites/run_radar_sites.py
python sites/radar_sites/compare_model_pit_radar.py
```

Preparation reuses and validates complete existing inputs. It refuses to
replace partial setups or inputs generated with different settings; use
`--output-root /tmp/jif_forcing` to prepare a separate copy. The run script
accepts `--workers`, `--sites`, and `--forcings` and writes logs/status JSON under each model
site's `logs/`. Running it again restarts the selected simulations and replaces
their WY2020–WY2026 outputs. Raw TKG4 and DG1 use a documented, build-specific
[empty-column numerical guard](sites/radar_sites/numerics/README.md) to avoid
a SNOWPACK 3.7.0 vapor-transport crash; their forcing and physical configurations
remain unchanged.

Inputs are the existing merged WY2020–WY2026 UTM HRRR file and
`/hdd/snow_hydrology/JIF_radar/jif_snow_pit_sites_2021.csv`. Site elevations
are 1,326 m (TKG2), 1,203 m (TKG3), 1,483 m (C161), and 1,018 m (DG1). TKG4 retains its
existing model coordinates and 1,120 m elevation rather than the pit location.
Extraction uses the containing stored UTM cell. Temperature alone is corrected:
`TA_site = TA_HRRR - 0.006 * (z_site - z_HRRR)`. Stored HRRR orography varies
with time, so this correction uses each hour's value. The paired variants have
identical relative humidity, wind, radiation, pressure, and precipitation.

Files are under `/home/cassie/python/models/run_snowpack/sites/<site>/`.
Each site's `input/{hrrrak,hrrrak_lapserate}_WY2020-WY2026/` contains matching
SMET, SNO, and metadata JSON files, with one config per variant in `config/`.
All ten configs use `EXPERIMENT = heatflux_soiltemp_zero`, `GEO_HEAT = 0`,
`SNP_SOIL = false`, `SOIL_FLUX = false`, and a fixed 273.15 K ground-temperature
generator, following the TKG4 template in `sites/radar_sites/templates/`.
The common simulation range is 2019-10-01 05:00 to 2026-09-29 04:00 UTC,
which is the available source coverage rather than a complete final water year.
The source lacks 2024-05-23 03:00 UTC; that hour remains nodata in the input
files, with no zero-filled precipitation.

Initial profiles are empty, with flat terrain at the new sites and TKG4's
existing 38° slope. Substrate albedo is 0.4; ice/firn layers are not supplied.
Pit and radar coordinates provisionally use EPSG:32608; vertical datum is
unconfirmed. The comparison preserves archived pit dates separately from radar
acquisition dates: July 13 for TKG3/TKG4 and July 15 for C161 from the supplied
Table 1. TKG2 and DG1 have unresolved radar dates and use the July 9–15 campaign
window. Pit/radar seasonal snow is compared descriptively with modeled total
columns and an explicitly labeled autumn-minimum depth approximation.
Plots display inline without automatic image exports.

For radar exploration, select the **JIF snow modeling** kernel and open
[`radar/01_explore_radar_2021.ipynb`](radar/01_explore_radar_2021.ipynb).
See [environment setup](envs/README.md) to recreate the environment.

## Existing workflow

1. Use `jif_domain/01_open_single_grib_file.ipynb` to inspect HRRR-AK fields,
   then `01_process_hrrrak_grib_files.ipynb` to process the selected water years.
   `01_combine_arctic_dem_tiles.ipynb` prepares terrain data separately.
   See [terrain preparation and coverage notes](jif_domain/README.md) for the
   six-tile mosaic workflow, radar coverage checks, and shaded terrain
   maps with basemap context.
2. Use `jif_domain/02_merge_netcdfs.ipynb` to merge water years and extract
   point data. The `03_icefield_domain_*` notebooks map the domain and sites.
3. Use each site's `2_create_snowpack_smet_forcing_*` notebooks to prepare SMET
   forcing. Choose the intended water-year variant rather than running all
   variants as a sequence.
4. Run SNOWPACK separately using the model-run setup in
   `/home/cassie/python/models/run_snowpack/sites/<site>/`.
5. Use the site `3_read_snowpack_output_*` notebooks for analysis. The MLD4
   notebook with `TKG4_MLD4_SWE` in its name compares both sites; TKG4 also has a
   `4_read_snowpack_output_other_files.ipynb` exploration notebook.

## Data, environments, and paths

Radar source data remain at `/hdd/snow_hydrology/JIF_radar`; see
[radar/README.md](radar/README.md). HRRR-AK inputs and intermediate NetCDF files
remain under `/hdd/snow_hydrology/hrrrak/`, and terrain inputs under
`/hdd/snow_hydrology/DEMs/`. Large source data and model outputs are not copied
into this repository.

Most imported notebooks still use their original paths. The terrain merge and
viewing notebooks use the mosaic products documented in `jif_domain/README.md`.
**Check input and export paths before executing cells.** Forcing notebooks still
write into the original `run_snowpack` tree, and analysis notebooks read its
outputs. Older TKG4 variants reference `large_juneau_domain` and use a mix of
`WY2024-WY2025` and `WY2024-25` naming. They are retained as starting workflows,
not verified final run configurations. The WY2020–WY2026 setup above replaces the earlier six-year forcing setup; existing analysis notebooks still refer to historical outputs.

Notebook headers identify the original environments: `rasterio` for shared
domain and forcing work, and `xarray` for site output analyses. The new
`jif_snow_modeling` environment is a separate clone of the installed `rasterio`
environment, recorded in `envs/`. The `xarray` environment and SNOWPACK
configuration/input files have not been imported yet. Legacy imported notebooks remain unverified end to end. The consolidated
five-site workflow above has been executed: all ten outputs have 61,320
hourly records with matching start/end dates and finite snow depth/SWE.

All 16 notebooks were copied from the corresponding `snow_modeling_point`
folders (the source `icefield_domain/` folder is named `jif_domain/` here) on 2026-10-28. Original files were left untouched.
`docs/import_manifest.csv` records the source paths, sizes, and SHA-256 checksums
at import; it is a provenance snapshot, not a checksum list to maintain as the
new workflows evolve.

Superseded six-year model inputs and configurations are retained locally under
`/home/cassie/python/models/run_snowpack/temporary/wy2025_setups/`. Existing
TKG4 results are preserved for the historical pit/radar comparison notebooks.

## Visualization conventions

Use `sites/radar_sites/visualization.py` for the shared plotting settings:
**HRRR-AK Raw** is maroon and **HRRR-AK Lapserate** is royalblue. Total snow/firn depth is faded and dashed; autumn-minimum-adjusted
depth is solid. Both use thicker lines. Observations
are black: circles for snow pits and squares for radar. Comparison legends
sit below the panels in multiple columns, with larger axis and legend text.
The forcing notebook includes the [Markdown site metadata table](sites/radar_sites/site_summary.md),
including DG1, elevation ranges, collection dates, and nearest-radar distances.
