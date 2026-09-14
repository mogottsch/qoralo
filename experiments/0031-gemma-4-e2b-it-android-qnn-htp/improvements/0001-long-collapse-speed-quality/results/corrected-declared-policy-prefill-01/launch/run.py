from pathlib import Path
import json,sys
TRACK=Path('/home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality');ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(TRACK/'tools'))
from run_corrected_paired_prefill_host import load_adapter
module,binding=load_adapter();(ROOT/'adapter-binding.json').write_text(json.dumps(binding,indent=2)+'\n')
sys.argv=[sys.argv[0],'--execute','--run-id','corrected-ref-20260914T082259Z-01','--pi-grant','pi-gemma-corrected-fp16-20260914-01','--phone-collection','/home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/.local/legacy-logits-phone-runs/legacy-prefill-20260913T125558Z-01/collection.json']
result={'actual_host_controller_exit':1}
try:result['actual_host_controller_exit']=module.main()
except Exception as error:result.update(error_type=type(error).__name__,error=str(error))
finally:(ROOT/'controller-exit.json').write_text(json.dumps(result,indent=2)+'\n')
raise SystemExit(result['actual_host_controller_exit'])
