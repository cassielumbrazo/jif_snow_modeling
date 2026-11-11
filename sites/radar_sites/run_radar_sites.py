"""Run the radar-site simulations over one common UTC period."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import argparse
import json
import hashlib
import shutil
import re
import pandas as pd
from prepare_radar_site_forcing import read_smet, SITES
import subprocess
from datetime import datetime, timezone

FORCINGS = ('hrrrak', 'hrrrak_lapserate')
START = '2019-10-01T05:00'
END = '2026-09-29T04:00'
MODEL_ROOT = Path('/home/cassie/python/models/run_snowpack/sites')


def run_one(job):
    site, forcing, root = job
    station = f'{forcing}_{site}_WY2020-WY2026'
    log_dir = root/site/'logs'
    log_dir.mkdir(exist_ok=True)
    log = log_dir/f'{station}.log'
    command = ['snowpack', '-c', station+'.ini', '-b', START, '-e', END]
    numerical_guard = None
    if site in {'tkg4','dg1'} and forcing == 'hrrrak':
        binary = Path(shutil.which('snowpack')).resolve()
        library = binary.parent.parent/'lib/libsnowpack.so.3.7.0'
        expected_hash = 'f1c11a0ac7e3c9b88810370f0e012f946a5b70073879a400f6f751cde897908f'
        if hashlib.sha256(library.read_bytes()).hexdigest() != expected_hash:
            raise RuntimeError('The empty-column guard is specific to the recorded SNOWPACK build; review before running.')
        numerical_guard = str(Path(__file__).resolve().parent/'numerics/empty_snow_vapour_guard.gdb')
        command = ['gdb', '-batch', '-x', numerical_guard, '--args', str(binary), *command[1:]]
    started = datetime.now(timezone.utc).isoformat()
    with log.open('w') as stream:
        result = subprocess.run(command, cwd=root/site/'config', stdout=stream, stderr=subprocess.STDOUT)
    text = log.read_text(errors='replace')
    record = dict(site=site, forcing=forcing, start_UTC=START, end_UTC=END,
                  started_at_UTC=started, finished_at_UTC=datetime.now(timezone.utc).isoformat(),
                  command=command, numerical_guard=numerical_guard, returncode=result.returncode, log=str(log),
                  finished_message='FINISHED running' in text)
    guard_counts = re.findall(r'Empty-column LayerToLayer guards: (\d+)', text)
    record['empty_column_guard_count'] = int(guard_counts[-1]) if guard_counts else 0
    if record['finished_message']:
        path = root/site/'output'/f'{station}_heatflux_soiltemp_zero.smet'
        _, frame = read_smet(path, ['timestamp','HS_mod','SWE'])
        expected = pd.date_range(START, END, freq='h')
        record['output_rows'] = len(frame)
        record['output_complete'] = frame.index.equals(expected) and not frame.isna().any().any()
    else:
        record['output_complete'] = False
    log.with_suffix('.json').write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps(record), flush=True)
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-root', type=Path, default=MODEL_ROOT)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--sites', nargs='+', choices=SITES, default=list(SITES))
    parser.add_argument('--forcings', nargs='+', choices=FORCINGS, default=list(FORCINGS))
    args = parser.parse_args()
    jobs = [(s, f, args.model_root) for s in args.sites for f in args.forcings]
    for s,f,r in jobs:
        if not (r/s/'config'/f'{f}_{s}_WY2020-WY2026.ini').is_file():
            raise FileNotFoundError((s,f))
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(run_one, jobs))
    if any(r['returncode'] or not r['finished_message'] or not r['output_complete'] for r in results):
        raise SystemExit('Some simulations failed; inspect the per-run logs.')
