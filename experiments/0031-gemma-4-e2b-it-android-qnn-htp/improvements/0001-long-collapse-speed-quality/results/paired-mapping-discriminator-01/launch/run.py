from pathlib import Path
import sys,json
TRACK=Path('/home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality');ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(TRACK/'tools'))
from phone_mapping_stage_capture import load_adapter,DIGEST
controller,binding=load_adapter();(ROOT/'adapter-binding.json').write_text(json.dumps(binding,indent=2)+'\n')
sys.argv=[sys.argv[0],'--execute','--reviewed-stage-digest',DIGEST,'--pi-slot','pi-gemma-mapping-20260913T103155Z-01','--run-id','mapping-20260913T103155Z-01','--expected-app-sha256','7989af04ab9e63dab4c97e4d515382c11852f2b97a8089e8bd673a581a7db82d','--expected-test-sha256','27e8d84c1640f6494fb25d59cc22b79849e83ccb8f62218736faacd64b6da279','--pi-user-job-quiescent']
result=controller.main();(ROOT/'controller-exit.json').write_text(json.dumps({'actual_controller_exit':result})+'\n');raise SystemExit(result)
