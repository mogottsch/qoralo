from pathlib import Path
import sys,json
TRACK=Path('/home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality');ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(TRACK/'tools'))
from phone_mapping_as12_capture import load_adapter
controller,binding=load_adapter();(ROOT/'adapter-binding.json').write_text(json.dumps(binding,indent=2)+'\n')
sys.argv=[sys.argv[0],'--execute','--reviewed-stage-digest',controller.STAGE_DIGEST,'--pi-slot','pi-gemma-mapping-as12-20260913T104909Z-01','--run-id','mapping-as12-20260913T104909Z-01','--expected-app-sha256','939c731e75a47c535cce130474b5d734d05a6765879f036085396cb97ed1023c','--expected-test-sha256','1b2ef1c156233b1542f0b891eeacf1011a7d80b10bfd87ed814c21188ef1612f','--pi-user-job-quiescent']
result=controller.main();(ROOT/'controller-exit.json').write_text(json.dumps({'actual_controller_exit':result})+'\n');raise SystemExit(result)
