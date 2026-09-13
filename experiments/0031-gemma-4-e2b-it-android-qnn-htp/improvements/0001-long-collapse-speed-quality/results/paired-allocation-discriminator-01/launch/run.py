from pathlib import Path
import sys,json
TRACK=Path('/home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality');ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(TRACK/'tools'))
from phone_allocation_stage_capture import load_adapter,DIGEST
controller,binding=load_adapter();(ROOT/'adapter-binding.json').write_text(json.dumps(binding,indent=2)+'\n')
sys.argv=[sys.argv[0],'--execute','--reviewed-stage-digest',DIGEST,'--pi-slot','pi-gemma-allocation-20260912T144721Z-01','--run-id','allocation-20260912T144721Z-01','--expected-app-sha256','da9d015ebc69c5ee535abe6f84ccf9e07b1d16f17443b3795d2aa45086c2ee27','--expected-test-sha256','173e4744fb30de9d778bbe84bf81e51f38e8df31295e92becd8aa3ce20a718bd','--pi-user-job-quiescent']
code=controller.main();(ROOT/'controller-exit.json').write_text(json.dumps({'actual_controller_exit':code})+'\n');raise SystemExit(code)
