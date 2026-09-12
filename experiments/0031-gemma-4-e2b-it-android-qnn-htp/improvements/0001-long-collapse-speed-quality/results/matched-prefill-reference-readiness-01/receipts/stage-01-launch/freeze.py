from pathlib import Path
import sys,json
sys.path.insert(0,'/home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/tools')
from prepare_paired_prefill_capture import freeze_stage
r=freeze_stage(Path('/home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/.local/frozen-stages/paired-prefill-capture-stage-01'))
Path('/home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/.local/paired-prefill-capture/stage-01-launch/stage-result.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r))
