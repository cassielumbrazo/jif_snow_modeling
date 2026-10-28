# Juneau Icefield terrain and domain workflows

Use the **JIF snow modeling** kernel for these terrain notebooks.

1. [`01_combine_arctic_dem_tiles.ipynb`](01_combine_arctic_dem_tiles.ipynb) discovers
   raw tiles, creates the mosaics, and checks radar coverage and missing pixels.
2. [`01_open_jif_dem_mosaic.ipynb`](01_open_jif_dem_mosaic.ipynb) opens the clean
   mosaics and plots shaded elevation, radar tracks, and basemap context.

The regional extent comes from the **six downloaded tile footprints**. There is
no separately requested geographic rectangle. The detailed DEM covers the radar
footprint plus a 5 km buffer.

## Data and outputs

Raw 2 m tiles remain in subfolders of:

```text
/hdd/snow_hydrology/DEMs/ArcticDEM/
```

Mosaic products and diagnostic tables are written to:

```text
/hdd/snow_hydrology/DEMs/ArcticDEM_edits/icefield_domain/jif_mosaic/
```

| Active product | Purpose |
| --- | --- |
| `jif_arcticdem_native_2m.vrt` | Original tiles combined in their native EPSG:3413 grid |
| `jif_tiles_utm8n_2m.vrt` | Six-tile extent in EPSG:32608, evaluated on demand |
| `jif_tiles_utm8n_20m.tif` | Six-tile regional terrain, averaged to 20 m |
| `jif_radar_utm8n_2m.tif` | Radar tracks and 5 km buffer, at 2 m |
| `tile_inventory.csv` | Raw tile paths and metadata |
| `tile_extent_processing_manifest.json` | Inputs, settings, and provenance for reusable products |
| `tile_extent_dem_quality_summary.csv` | Exact output-cell validity counts |
| `tile_extent_radar_coverage_summary.csv` | Radar-location coverage checks |
| `tile_extent_radar_dem_samples.csv` | Elevation samples at finite radar coordinates |

The regional GeoTIFF uses **average** resampling; the 2 m UTM products use
**bilinear** resampling. Every product is reprojected from the native mosaic,
with source nodata excluded. No void filling or vertical datum conversion is
performed. Original files and earlier experiments are left in place; use the
active `jif_tiles_` products rather than older `jif_domain_` products.

VRTs depend on original local source paths. The 20 m GeoTIFF does not retain
native 2 m detail. Raster grids have rectangular outer bounds; small corners
outside the actual tile footprints remain nodata.

## Terrain maps

The opening notebook creates a regional view and a radar-area close-up with:

- Shaded elevation using lightweight previews of the clean DEMs.
- Every radar point with finite coordinates, without sampling or deduplication.
- Natural Earth coastlines, lakes, land, and ocean via Cartopy.

Saved figures go to `jif_domain/figures/`, ignored by Git, and are embedded in
the executed notebook. Cartopy uses its local map-data cache and downloads
missing shapefiles when needed.

## Interpretation

- Both notebooks were executed successfully. All 119,218 radar locations have
  valid elevation samples in the native mosaic and both active GeoTIFFs.
- The radar readme specifies UTM Zone 8N without its datum. The overlay assumes
  WGS 84 provisionally; confirm that before precise spatial matching.
- Source voids remain missing. Use the exact QA tables for coverage counts;
  downsampled previews can miss small holes.
- ArcticDEM mosaics combine source dates and should not be interpreted as
  contemporaneous 2021 glacier surface observations.
- Other imported domain notebooks retain their original paths and have not
  automatically been redirected to these mosaics.
