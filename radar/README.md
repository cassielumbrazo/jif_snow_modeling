# Radar analysis

Source data are stored outside Git at `/hdd/snow_hydrology/JIF_radar`.
The initial inventory on 2026-10-28 is:

| File | Size (bytes) | Role |
| --- | --- | --- |
| `ml_swe_2021.csv` | 19412230 | Dataset to inspect for radar/model comparison |
| `readme_jif_ml_data.docx` | 141131 | Accompanying data documentation |

Start with [01_explore_radar_2021.ipynb](01_explore_radar_2021.ipynb), using the
**JIF snow modeling** kernel; see [environment setup](../envs/README.md).
It inventories columns and profiles, checks missing values, duplicates and unit
consistency, plots all finite-coordinate points, and explores distributions and
elevation relationships. No rows are silently removed from the source dataset.

The accompanying document specifies UTM Zone 8N coordinates in metres but does
not identify the datum. Maps therefore use the supplied projected coordinates
without a geographic transformation. A separate basemap version assumes
**WGS 84 / UTM Zone 8N (EPSG:32608)** provisionally and labels that assumption.
It uses Natural Earth coastlines, land, ocean, and lakes via Cartopy, with a
30 km margin around the radar footprint. Cartopy uses cached map data or
downloads missing shapefiles on first use. Confirm the datum before using the
overlay for spatial matching or quantitative analysis.

The notebook saves `radar_2021_point_maps.png` and
`radar_2021_point_maps_basemap.png` alongside the distribution and elevation
plots in the ignored `radar/figures/` folder. Plots are also embedded in the
executed notebook.

Initial inspection found 119,218 rows across nine profiles, 180 exact duplicate
rows, and 7,417 rows with missing travel time/depth but numeric SWE in metres.
These are flagged for investigation, not automatically cleaned. The notebook
also compares the metre and centimetre columns. The CSV contains no acquisition
timestamp column; observation timing and uncertainty need confirmation before
model validation.

Keep new inspection, mapping, and comparison notebooks here. Leave the source
files unchanged; put local derived datasets in `data/` and plots in `figures/`
under this folder, both ignored by Git.
