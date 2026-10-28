# JIF Python environment

`jif_snow_modeling` was created on 2026-10-28 by cloning the installed `rasterio`
environment. The original environment was left unchanged. The new environment
contains Python 3.13.1 and the same 272 Conda packages, including pandas,
Matplotlib, GeoPandas, Rasterio, Cartopy, xarray, and ipykernel.

## Use the environment on this machine

```bash
conda activate jif_snow_modeling
```

In VS Code, select **JIF snow modeling** as the kernel for
`radar/01_explore_radar_2021.ipynb`. Its interpreter is
`/home/cassie/programs/miniforge3/envs/jif_snow_modeling/bin/python`.
The kernel is registered with Jupyter under `jif_snow_modeling`.

## Recreate elsewhere

Install Conda (for example via Miniforge), then run from the repository root:

```bash
conda env create --file envs/jif_snow_modeling.yml
conda activate jif_snow_modeling
python -m ipykernel install --user --name jif_snow_modeling --display-name "JIF snow modeling"
```

The YAML is a full installed environment export from the new clone, with package
versions and build identifiers preserved and the machine-specific `prefix:`
removed. It targets Linux x86_64; it is not a portable macOS/Windows export.
Recreation depends on those package builds remaining available from conda-forge.
The actual environment here was cloned locally, rather than recreated by
solving this YAML on another machine.

For reference, the original cloning command was:

```bash
conda create --name jif_snow_modeling --clone rasterio --offline --yes
```

After intentionally changing this environment, refresh its record:

```bash
conda env export --name jif_snow_modeling > envs/jif_snow_modeling.yml
```

Remove the final `prefix:` line and update the snapshot date before committing.
No radar data, terrain data, or SNOWPACK executable are installed by this
environment file. The radar basemap uses Cartopy's Natural Earth shapefile
cache; uncached basemap features require internet access on first use.
Imported site output notebooks originally use a separate
`xarray` environment and have not been validated in this clone.
