# Juneau Icefield snow modeling

Point and future distributed snow modeling on the Juneau Icefield, with radar
snow observations for comparison. This working repository starts from the MLD4
and TKG4 workflows in
[snow_modeling_point](https://github.com/cassielumbrazo/snow_modeling_point).

| Folder | Purpose |
| --- | --- |
| `sites/mld4/` | MLD4 forcing preparation and model-output analysis |
| `sites/tkg4/` | TKG4 forcing preparation and model-output analysis |
| `jif_domain/` | Existing shared HRRR-AK processing, DEM preparation, point extraction, and domain maps |
| `radar/` | Radar data inventory, exploration notebook, and point maps |
| `envs/` | JIF Python environment snapshot and setup instructions |
| `docs/` | Import provenance |

Add new point simulations under `sites/<site_id>/`, keeping site-specific forcing
and analysis together. Keep processing shared across sites in `jif_domain/`.
Add a distributed modeling folder when that work begins.

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
not verified final run configurations.

Notebook headers identify the original environments: `rasterio` for shared
domain and forcing work, and `xarray` for site output analyses. The new
`jif_snow_modeling` environment is a separate clone of the installed `rasterio`
environment, recorded in `envs/`. The `xarray` environment and SNOWPACK
configuration/input files have not been imported yet. The imported modeling
workflow has not been rerun end to end.

All 16 notebooks were copied from the corresponding `snow_modeling_point`
folders (the source `icefield_domain/` folder is named `jif_domain/` here) on 2026-10-28. Original files were left untouched.
`docs/import_manifest.csv` records the source paths, sizes, and SHA-256 checksums
at import; it is a provenance snapshot, not a checksum list to maintain as the
new workflows evolve.
