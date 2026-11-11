# Radar-site summary

## Site metadata

Coordinates below locate the model points; all except TKG4 coincide with the pits. “Site/model elevation” is the configured recorded elevation, not an independently verified ground truth. Pit and radar horizontal datum is provisionally EPSG:32608; vertical datum is unconfirmed. HRRR-AK orography varies with time, so its full forcing-period range and the corresponding temperature-correction range are shown.

| Site | Model latitude (°N) | Model longitude (°E) | Site/model elevation (m) | Pit elevation (m) | HRRR-AK elevation range (m) | TA correction range (K) | Pit collection date | Radar collection date | Pit → nearest radar sample (m) | Model → pit (m) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TKG2 | 58.688654 | -134.382797 | 1326 | 1326 | 1228.6–1300.2 | -0.58 to -0.15 | 2021-07-15 | Unresolved (campaign: 2021-07-09–15) | 1.8 | 0.0 |
| TKG3 | 58.656386 | -134.277751 | 1203 | 1203 | 1078.6–1156.2 | -0.75 to -0.28 | 2021-07-09 | 2021-07-13 | 6.4 | 0.0 |
| C161 | 58.632957 | -134.418588 | 1483 | 1483 | 1516.2–1533.4 | +0.20 to +0.30 | 2021-07-15 | 2021-07-15 | 23.3 | 0.0 |
| TKG4 | 58.634470 | -134.237080 | 1120 | 1067 | 995.6–1055.8 | -0.75 to -0.39 | 2021-07-07 depth; 2021-07-08 SWE | 2021-07-13 | 16.0 | 8.3 |
| DG1 | 58.617588 | -134.130047 | 1018 | 1018 | 1003.4–1041.8 | -0.09 to +0.14 | 2021-07-10 | Unresolved (campaign: 2021-07-09–15) | 11.1 | 0.0 |

Distances are horizontal UTM distances to the nearest **recorded radar sample**, not a perpendicular distance to an inferred continuous track. They use all finite radar coordinates. A small distance does not establish matching elevation, acquisition date, or independent samples. The comparison uses a separate 500 m pit-centered radar footprint and reports its radius sensitivity.

TKG4 depth was observed on July 7 and density/SWE on July 8; its radar date is July 13. TKG3's archived July 9 pit date differs from the supplied Table 1 ground-truth date. TKG2 and DG1 radar dates remain unresolved; their campaign window is not an exact acquisition date.

Regenerate this table with `python sites/radar_sites/site_metadata.py` after changing site metadata.


## Shared workflow and model locations

All five radar sites (DG1, TKG4, TKG3, TKG2, and C161) use the same workflow:

- [Review forcing and site elevations](01_review_radar_site_forcing.ipynb).
- [Compare model depth/SWE with pits and radar](02_compare_model_pit_radar_WY2021.ipynb).
- Prepare or reuse forcing with `prepare_radar_site_forcing.py`; run simulations with `run_radar_sites.py`.

Inputs, configurations, logs, and results remain outside this repository at
`/home/cassie/python/models/run_snowpack/sites/<site>/`, where `<site>` is
`dg1`, `tkg4`, `tkg3`, `tkg2`, or `c161`. Each has raw and lapse-rate variants
for WY2020–WY2026. Removing redundant repository folders does not remove those
model files.

DG1 is the Demorest Branch pit on Taku Glacier, with a recorded elevation of
1,018 m and archived pit date of 10 July 2021. Its radar date remains unresolved.
TKG4 retains its established model point and configuration; the table above
records the pit/model elevation difference and separation explicitly.

The repository retains `sites/mld4/` and `sites/tkg4/` for their older forcing
and analysis notebooks. Other radar-site notes are consolidated here.
