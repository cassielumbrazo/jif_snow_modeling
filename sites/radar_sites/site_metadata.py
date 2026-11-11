"""Site metadata and distances for the forcing review Markdown table."""
import numpy as np
import pandas as pd
from pyproj import Transformer
from prepare_radar_site_forcing import SITES, MODEL_ROOT, load_prepared
from compare_model_pit_radar import load_pits, RADAR_ROOT, RADAR_WINDOWS


def site_summary(model_root=MODEL_ROOT):
    pits=load_pits()
    radar=pd.read_csv(RADAR_ROOT/'ml_swe_2021.csv',encoding='utf-8-sig',usecols=['east','north']).dropna()
    xy=radar[['east','north']].to_numpy()
    xy=xy[np.isfinite(xy).all(axis=1)]
    transform=Transformer.from_crs(4326,32608,always_xy=True)
    rows=[]
    for site in SITES:
        meta,_,_=load_prepared(site,model_root)
        pit=pits.loc[site]
        x,y=transform.transform(meta['longitude'],meta['latitude'])
        distance=np.hypot(xy[:,0]-pit.east,xy[:,1]-pit.north)
        exact=site not in {'tkg2','dg1'}
        radar_date=RADAR_WINDOWS[site][0] if exact else 'Unresolved (campaign: 2021-07-09–15)'
        pit_date=pit.pit_date.strftime('%Y-%m-%d')
        if pit.pit_swe_date!=pit.pit_date:
            pit_date+=' depth; '+pit.pit_swe_date.strftime('%Y-%m-%d')+' SWE'
        rows.append(dict(site=site.upper(),latitude=meta['latitude'],longitude=meta['longitude'],
                         model_elevation_m=meta['elevation_m'],pit_elevation_m=pit.elevation_m,
                         hrrr_elevation_min_m=meta['hrrr_elevation_min_m'],hrrr_elevation_max_m=meta['hrrr_elevation_max_m'],
                         correction_min_K=meta['correction_min_K'],correction_max_K=meta['correction_max_K'],
                         pit_date=pit_date,radar_date=radar_date,
                         pit_to_nearest_radar_sample_m=float(distance.min()),model_to_pit_m=float(np.hypot(x-pit.east,y-pit.north))))
    return pd.DataFrame(rows)


def summary_markdown(summary):
    headers=['Site','Model latitude (°N)','Model longitude (°E)','Site/model elevation (m)',
             'Pit elevation (m)','HRRR-AK elevation range (m)','TA correction range (K)',
             'Pit collection date','Radar collection date','Pit → nearest radar sample (m)','Model → pit (m)']
    lines=['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']
    for r in summary.itertuples():
        values=[r.site,f'{r.latitude:.6f}',f'{r.longitude:.6f}',f'{r.model_elevation_m:.0f}',f'{r.pit_elevation_m:.0f}',
                f'{r.hrrr_elevation_min_m:.1f}–{r.hrrr_elevation_max_m:.1f}',f'{r.correction_min_K:+.2f} to {r.correction_max_K:+.2f}',
                r.pit_date,r.radar_date,f'{r.pit_to_nearest_radar_sample_m:.1f}',f'{r.model_to_pit_m:.1f}']
        lines.append('| '+' | '.join(values)+' |')
    return '\n'.join(lines)


if __name__ == '__main__':
    print(summary_markdown(site_summary()))
