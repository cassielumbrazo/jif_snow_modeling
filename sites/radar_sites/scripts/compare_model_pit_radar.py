"""Load paired SNOWPACK simulations and descriptive 2021 pit/radar comparisons."""
from pathlib import Path
import csv
import json
import numpy as np
import pandas as pd
from prepare_radar_site_forcing import read_smet, load_prepared, MODEL_ROOT, PERIOD, SITES

FORCINGS = ('hrrrak', 'hrrrak_lapserate')
RADAR_ROOT = Path('/hdd/snow_hydrology/JIF_radar')
# Exact radar dates for the other sites are absent from the source CSV.
RADAR_WINDOWS = {s: ('2021-07-09', '2021-07-16') for s in SITES}
RADAR_WINDOWS['tkg4'] = ('2021-07-13', '2021-07-14')
RADAR_WINDOWS['tkg3'] = ('2021-07-13', '2021-07-14')
RADAR_WINDOWS['c161'] = ('2021-07-15', '2021-07-16')


def load_pits(root=RADAR_ROOT):
    inventory = pd.read_csv(root/'jif_snow_pit_sites_2021.csv').set_index('site_id')
    result = []
    for site in SITES:
        source = root/'snowpits'/f'2021_Mass_Balance_{site.upper()}.csv'
        with source.open(encoding='utf-8-sig', newline='') as f:
            rows = list(csv.reader(f))
        def row(label):
            return next(r for r in rows if r and r[0].strip() == label)
        depth = row('Pit Depth (cm):')
        location = next(i for i,r in enumerate(rows) if r and r[0].startswith('Location('))
        pit_date = pd.to_datetime(row('Date:')[1])
        swe_date = pit_date
        if site == 'tkg4':
            if 'sampled on 07/08/21' not in source.read_text(encoding='utf-8-sig'):
                raise ValueError('Review TKG4 density sampling date in the field notes')
            swe_date = pd.Timestamp('2021-07-08')
        result.append(dict(site=site, pit_date=pit_date, pit_swe_date=swe_date,
                           east=float(rows[location+1][1]), north=float(rows[location+1][2]),
                           elevation_m=float(row('Elevation(m):')[1]), depth_cm=float(depth[1]),
                           swe_mm=float(depth[4])*10, source=str(source),
                           quality_flags=str(inventory.loc[site.upper(), 'quality_flags']) if pd.notna(inventory.loc[site.upper(), 'quality_flags']) else ''))
    return pd.DataFrame(result).set_index('site')


def load_models(root=MODEL_ROOT):
    models, audit = {}, []
    for site in SITES:
        for forcing in FORCINGS:
            station = f'{forcing}_{site}_{PERIOD}_heatflux_soiltemp_zero'
            path = Path(root)/site/'output'/f'{station}.smet'
            header, frame = read_smet(path, ['timestamp', 'HS_mod', 'SWE'])
            fields = header['fields'].split()
            multipliers = header['units_multiplier'].split()
            units = header['plot_unit'].split()
            if float(multipliers[fields.index('HS_mod')]) != .01 or units[fields.index('HS_mod')] != 'm':
                raise ValueError(f'Review snow-depth units in {path}')
            if float(multipliers[fields.index('SWE')]) != 1 or units[fields.index('SWE')] != 'kg/m2':
                raise ValueError(f'Review SWE units in {path}')
            # Raw HS_mod is cm; raw SWE is kg/m² = mm water equivalent.
            frame = frame.rename(columns={'HS_mod':'depth_cm', 'SWE':'swe_mm'})
            expected = pd.date_range('2019-10-01T05:00', '2026-09-29T04:00', freq='h')
            missing = expected.difference(frame.index)
            if len(missing) or frame.index.min()!=expected.min() or frame.index.max()!=expected.max():
                raise ValueError(f'Incomplete model output: {path}; {len(missing)} missing hours')
            if frame.isna().any().any():
                raise ValueError(f'Missing output values: {path}')
            models[(site,forcing)] = frame
            audit.append(dict(site=site, forcing=forcing, start_UTC=frame.index.min(),
                              end_UTC=frame.index.max(), rows=len(frame), path=str(path),
                              numerical_guard='Empty-column LayerToLayer guard' if site in {'tkg4','dg1'} and forcing=='hrrrak' else 'None'))
    return models, pd.DataFrame(audit)


def autumn_adjustments(models):
    """Fixed autumn depth baseline, not a modeled annual layer boundary."""
    adjusted, records = {}, []
    for (site,forcing), frame in models.items():
        output = frame.copy()
        output['water_year'] = frame.index.year + (frame.index.month>=10).astype(int)
        output['autumn_minimum_cm'] = np.nan
        for wy in output.water_year.unique():
            lo, hi = pd.Timestamp(int(wy)-1,8,1), pd.Timestamp(int(wy)-1,11,1)
            window = frame.loc[(frame.index>=lo)&(frame.index<hi),'depth_cm'].dropna()
            expected = pd.date_range(lo,hi,freq='h',inclusive='left')
            minimum = window.min() if len(window) else np.nan
            output.loc[output.water_year==wy,'autumn_minimum_cm'] = minimum
            records.append(dict(site=site,forcing=forcing,water_year=int(wy),
                                autumn_minimum_cm=minimum,minimum_date=window.idxmin() if len(window) else pd.NaT,
                                expected_hours=len(expected),available_hours=len(window),
                                complete=expected.isin(window.index).all()))
        output['depth_above_minimum_cm'] = output.depth_cm-output.autumn_minimum_cm
        adjusted[(site,forcing)] = output
    return adjusted,pd.DataFrame(records)


def local_radar(pits, root=RADAR_ROOT, radius=500):
    radar = pd.read_csv(root/'ml_swe_2021.csv', encoding='utf-8-sig')
    columns = ['east','north','twtt1','aa_avg_depth_m','aa_swe_avg_m']
    finite = pd.Series(np.isfinite(radar[columns].to_numpy()).all(axis=1),index=radar.index)
    valid = finite & radar.twtt1.gt(0) & radar.aa_avg_depth_m.ge(0) & radar.aa_swe_avg_m.ge(0)
    local, rows = {}, []
    for site,pit in pits.iterrows():
        distance = np.hypot(radar.east-pit.east,radar.north-pit.north)
        local[site] = radar.loc[valid & distance.le(radius)].copy()
        for r in sorted(set([100,250,500,1000,2000,radius])):
            selected = radar.loc[valid & distance.le(r)]
            row = dict(site=site,radius_m=r,rows=len(selected),
                       rejected_rows=int((distance.le(r)&~valid).sum()),
                       exact_duplicate_rows=int(selected.duplicated().sum()),
                       profiles=','.join(sorted(selected.profile.dropna().unique())))
            for column, scale, label in [('aa_avg_depth_m',100,'depth_cm'),('aa_swe_avg_m',1000,'swe_mm')]:
                for q,name in [(.1,'p10'),(.5,'median'),(.9,'p90')]:
                    row[f'{label}_{name}']=selected[column].quantile(q)*scale
            rows.append(row)
    return radar,local,pd.DataFrame(rows)


def comparison_tables(adjusted, pits, local, radar_windows=RADAR_WINDOWS):
    rows = []
    for (site,forcing),frame in adjusted.items():
        pit = pits.loc[site]
        a,b = map(pd.Timestamp,radar_windows[site])
        observations = [('Pit depth',pit.pit_date,pit.pit_date+pd.Timedelta(days=1),pit.depth_cm,np.nan,1,np.nan,np.nan),
                        ('Pit SWE',pit.pit_swe_date,pit.pit_swe_date+pd.Timedelta(days=1),np.nan,pit.swe_mm,1,np.nan,np.nan)]
        samples=local[site]
        if len(samples):
            q=samples.aa_avg_depth_m.quantile([.1,.5,.9])*100
            observations.append(('Radar',a,b,q.loc[.5],samples.aa_swe_avg_m.median()*1000,len(samples),q.loc[.1],q.loc[.9]))
        for source,start,end,depth,swe,n,p10,p90 in observations:
            selected=frame.loc[(frame.index>=start)&(frame.index<end)]
            expected=pd.date_range(start,end,freq='h',inclusive='left')
            complete=expected.isin(selected.index).all()
            rows.append(dict(site=site,forcing=forcing,observation=source,start_UTC=start,end_exclusive_UTC=end,
                             date_basis='Archived pit dig/sample date' if source.startswith('Pit') else ('User-supplied Table 1 radar date' if site not in {'tkg2','dg1'} else 'Campaign window; exact radar date unresolved'),
                             observation_count=n,expected_model_hours=len(expected),model_hours=len(selected),complete=complete,
                             observed_depth_cm=depth,observed_swe_mm=swe,radar_depth_p10_cm=p10,radar_depth_p90_cm=p90,
                             model_total_depth_mean_cm=selected.depth_cm.mean() if complete else np.nan,
                             model_adjusted_depth_mean_cm=selected.depth_above_minimum_cm.mean() if complete else np.nan,
                             model_depth_min_cm=selected.depth_cm.min(),model_depth_max_cm=selected.depth_cm.max(),
                             model_swe_mean_mm=selected.swe_mm.mean() if complete else np.nan))
    return pd.DataFrame(rows)


def snow_depth_statistics(comparisons):
    """Summarize adjusted-depth differences with equal weight per site/run/source."""
    rows = comparisons.loc[comparisons.observation.isin(['Pit depth', 'Radar'])].copy()
    if rows.duplicated(['site', 'forcing', 'observation']).any():
        raise ValueError('Duplicate site/run/observation comparisons')
    if not rows.complete.all():
        raise ValueError('Snow-depth statistics require complete model comparison windows')
    rows['model_minus_observed_cm'] = rows.model_adjusted_depth_mean_cm - rows.observed_depth_cm
    rows['absolute_difference_cm'] = rows.model_minus_observed_cm.abs()
    pit = rows.loc[rows.observation.eq('Pit depth'),
        ['site','forcing','start_UTC','observed_depth_cm','model_adjusted_depth_mean_cm','model_minus_observed_cm']].rename(columns={
            'start_UTC':'pit_date','observed_depth_cm':'pit_depth_cm',
            'model_adjusted_depth_mean_cm':'model_at_pit_cm','model_minus_observed_cm':'model_minus_pit_cm'})
    radar = rows.loc[rows.observation.eq('Radar'),
        ['site','forcing','start_UTC','end_exclusive_UTC','date_basis','observed_depth_cm',
         'model_adjusted_depth_mean_cm','model_minus_observed_cm']].rename(columns={
            'start_UTC':'radar_window_start','end_exclusive_UTC':'radar_window_end_exclusive',
            'date_basis':'radar_date_basis','observed_depth_cm':'radar_median_depth_cm',
            'model_adjusted_depth_mean_cm':'model_at_radar_cm','model_minus_observed_cm':'model_minus_radar_cm'})
    detail = pit.merge(radar,on=['site','forcing'],how='outer',validate='one_to_one')
    by_simulation = rows.groupby(['forcing','observation'],sort=False).agg(
        comparisons=('model_minus_observed_cm','count'),
        mean_bias_cm=('model_minus_observed_cm','mean'),
        mean_absolute_difference_cm=('absolute_difference_cm','mean'))
    by_source = rows.groupby('observation',sort=False).agg(
        comparisons=('model_minus_observed_cm','count'),
        mean_bias_cm=('model_minus_observed_cm','mean'),
        mean_absolute_difference_cm=('absolute_difference_cm','mean'))
    return dict(detail=detail, by_simulation=by_simulation, by_source=by_source,
                overall_mean_absolute_difference_cm=rows.absolute_difference_cm.mean(),
                comparisons=int(rows.absolute_difference_cm.count()))


def load_comparison(root=MODEL_ROOT, radius=500):
    pits=load_pits()
    models,audit=load_models(root)
    adjusted,baselines=autumn_adjustments(models)
    radar,local,sensitivity=local_radar(pits,radius=radius)
    comparisons=comparison_tables(adjusted,pits,local)
    return dict(pits=pits,models=models,adjusted=adjusted,run_audit=audit,baselines=baselines,
                radar=radar,local_radar=local,radius_sensitivity=sensitivity,comparisons=comparisons)


if __name__=='__main__':
    data=load_comparison()
    print(data['run_audit'].to_string(index=False))
    print(data['comparisons'].round(2).to_string(index=False))
    stats = snow_depth_statistics(data['comparisons'])
    print(stats['detail'].round(1).to_string(index=False))
    print(stats['by_simulation'].round(1).to_string())
    print(f"Overall mean absolute adjusted-depth difference: {stats['overall_mean_absolute_difference_cm']:.1f} cm")
