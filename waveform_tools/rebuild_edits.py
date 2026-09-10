"""Reconstruct edited WAVs from acquired source clips; no model requests."""
from pathlib import Path
import argparse,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
p=argparse.ArgumentParser()
p.add_argument('--source-root',required=True,help='Directory under which manifest original audio paths resolve')
p.add_argument('--output-root',required=True,help='Directory for edited audio paths; existing files are not overwritten')
a=p.parse_args()
try:
 from scripts.validate_counterfactual_audio import apply_operation
 import soundfile as sf
except ModuleNotFoundError as exc:
 raise SystemExit("Install waveform dependencies first: python -m pip install -r waveform_tools/requirements.txt") from exc
root=Path(__file__).resolve().parent
rows=[json.loads(s) for s in (root.parent/'data/final48_manifest.jsonl').read_text(encoding='utf-8').splitlines() if s.strip()]
original={x['id']:x for x in rows if x['condition']=='original'}
n=0
for row in rows:
 if row['condition']=='original':continue
 out=Path(a.output_root)/row['audio_path']
 if out.exists():raise FileExistsError(out)
 x,sr=sf.read(Path(a.source_root)/original[row['id']]['audio_path'],dtype='float64')
 op=row['intervention'];y=apply_operation(x,sr,op['op'],op['params'])
 out.parent.mkdir(parents=True,exist_ok=True);sf.write(out,y,sr,subtype='PCM_16');n+=1
print('Reconstructed',n,'edited WAVs. No inference was run.')
