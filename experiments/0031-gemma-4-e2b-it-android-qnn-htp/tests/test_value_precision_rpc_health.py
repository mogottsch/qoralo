"""No ADB: health classification and the inherited fake lock/cleanup path."""
import importlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

TRACK = Path(__file__).resolve().parents[1]/'improvements/0001-long-collapse-speed-quality'
sys.path.insert(0,str(TRACK/'tools'))
a = importlib.import_module('phone_value_precision_long_health')


class HealthTests(unittest.TestCase):
    def test_explicit_cdsp_failure_blocks_but_missing_telemetry_is_unknown(self):
        self.assertTrue(a.classify(b'SUBSYSTEM\tcdsp\tOFFLINE\n')['explicit_resource_blockers'])
        self.assertTrue(a.classify(b'SERVICE\tinit.svc.vendor.cdsprpcd\tstopped\n')['explicit_resource_blockers'])
        unknown = a.classify(b'SERVICE\tinit.svc.vendor.cdsprpcd\t\nSUBSYSTEM\tcdsp\tUNEXPOSED\n')
        self.assertFalse(unknown['explicit_resource_blockers'])
        self.assertFalse(unknown['functional_rpc_health_proven'])
        self.assertIsNone(unknown['observations'][0]['state'])

    def test_offline_cdsp_preserves_resource_error_without_launch(self):
        base = importlib.import_module('test_phone_return_controller')
        fake_long = importlib.import_module('test_phone_return_long')
        module, _ = a.load_lifecycle()
        with tempfile.TemporaryDirectory() as directory, patch.object(base,'module',module):
            root=Path(directory);stage=root/'stage';stage.mkdir();(stage/'SHA256SUMS').write_text('fake\n')
            fake=fake_long.LongFake();clock=base.FakeClock()
            fake.fail['preflight.rpc_readiness']=module.Reply(0,b'SUBSYSTEM\tcdsp\tOFFLINE\n')
            c=module.Controller(stage=stage,output_root=root/'runs',slot_root=root/'slots',lock_path=root/'phone.lock',
                transport=fake,clock=clock,stage_verifier=lambda *args:{'files':{'bin/genie-app':{},'exact-long.script':{}}})
            fake.controller=clock.controller=c
            result=c.run(execute=True,reviewed_digest=a.base.STAGE_DIGEST,pi_slot='fake',run_id='fake')
            self.assertIn('RPC_RESOURCE_NOT_READY',result['error']['message'])
            self.assertFalse(result['launch_command_attempted'])
            self.assertEqual(result['cleanup'],'verified_absent')
            self.assertTrue(result['raw_pull_completed'])
            self.assertTrue(result['phone_lock_released'])
            self.assertNotIn('process.launch',[op for op,_,_ in fake.calls])


if __name__=='__main__': unittest.main()
