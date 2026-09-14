from pathlib import Path
import sys,json
TRACK=Path('/home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality');ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(TRACK/'tools'))
from phone_htp_chain_discriminator import load_lifecycle
expected={'dev.vibevoice.podcast.internal':'bf53c566a160c018e56d19e0aac5e7f9578a6d3f168326fa82163bdcf1c7721c','dev.vibevoice.podcast.internal.test':'f1543993c2ff77441b3fd1e4c4fa131975a6a30bee2d347619a0adc646f3b0a4'}
module,binding=load_lifecycle(expected,True);(ROOT/'controller-binding.json').write_text(json.dumps(binding,indent=2)+'\n')
sys.argv=[sys.argv[0],'--execute','--reviewed-stage-digest',module.DIGEST,'--pi-slot','pi-gemma-htp-chains-20260914T160058Z-01','--run-id','htp-chains-20260914T160058Z-01']
result={'actual_controller_exit':1}
try:result['actual_controller_exit']=module.main()
except Exception as error:result.update(error_type=type(error).__name__,error=str(error))
finally:(ROOT/'controller-exit.json').write_text(json.dumps(result,indent=2)+'\n')
raise SystemExit(result['actual_controller_exit'])
