"""Compile/test actual runner's nonneural helpers, without linking/loading ORT."""
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
import wave

ROOT = Path(__file__).resolve().parents[1]


class RunnerContract(unittest.TestCase):
    def test_actual_cpp_layout_extent_and_pcm(self):
        compiler = shutil.which('g++')
        if not compiler:
            self.skipTest('host g++ unavailable')
        # ROOT=.../experiments/0037.../htp, parents[2] is repository.
        include = ROOT.parents[2]/'experiments/0010-supertonic-qnn-htp-feasibility/.local/onnxruntime-v1.27.1-source/include/onnxruntime/core/session'
        (ROOT/'.local').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='synthetic-runner-',dir=ROOT/'.local') as folder:
            folder = Path(folder)
            test = folder/'test.cc'
            test.write_text(f'''#define ORT_API_MANUAL_INIT
#define main unused_neural_runner_main
#include "{ROOT / 'phone/runner.cc'}"
#undef main
#include <cassert>
#include <limits>
#include <numeric>
int main(int argc,char**argv) {{
  assert(argc==2);
  auto extent=native_extent(19.881694793701172f,1.05f);
  assert(extent.length==272 && extent.mask_length==272);
  assert(extent.duration==18.934947967529297f);
  assert(extent.length*HOP>extent.predicted_frames);
  for(float bad:{{0.f,-1.f,100.f,std::numeric_limits<float>::quiet_NaN()}}) {{
    bool rejected=false; try {{ native_extent(bad,1.05f); }} catch(const std::exception&) {{ rejected=true; }} assert(rejected);
  }}
  for(int64_t length=1;length<=LB;++length) {{
    auto edges=native_edge_indices(length);
    for(size_t k=0;k<RADII.size();++k) {{
      int r=RADII[k]; assert(edges[k].size()==size_t(LB+2*r));
      for(int64_t j=0;j<LB+2*r;++j) {{
        int64_t want=j-r; if(want<0)want=0; if(want>=length)want=length-1;
        assert(edges[k][j]==want);
      }}
    }}
  }}
  std::vector<float> stream(144*10); std::iota(stream.begin(),stream.end(),0.f);
  std::vector<float> first(stream.begin(),stream.begin()+144*7);
  std::vector<float> second(stream.begin()+144*7,stream.end());
  auto a=channel_pad(first,144,7,512), b=channel_pad(second,144,3,512);
  for(int c=0;c<144;++c) for(int j=0;j<512;++j) {{
    assert(a[c*512+j]==(j<7?float(c*7+j):0.f));
    assert(b[c*512+j]==(j<3?float(144*7+c*3+j):0.f));
  }}
  bool rejected=false; try {{ channel_pad(first,144,7,6); }} catch(const std::exception&) {{ rejected=true; }} assert(rejected);
  wav(fs::path(argv[1])/"synthetic.wav",std::vector<float>{{-2.f,-1.f,-0.5f,-1.f/32768.f,0.f,0.5f,1.f,2.f}});
  assert(!fs::exists(fs::path(argv[1])/"synthetic.wav.tmp"));
}}
''')
            subprocess.run([compiler,'-std=c++17','-O2','-ffp-contract=off','-ffunction-sections','-fdata-sections',
                '-Wl,--gc-sections','-I'+str(include),str(test),'-o',str(folder/'test')],check=True,capture_output=True,timeout=60)
            # The discarded neural entrypoint is never called and no ORT shared
            # library is linked. Only layout, scalar arithmetic and synthetic PCM.
            subprocess.run([str(folder/'test'),str(folder)],check=True,timeout=10)
            with wave.open(str(folder/'synthetic.wav'),'rb') as f:
                self.assertEqual((f.getnchannels(),f.getsampwidth(),f.getframerate(),f.getnframes()),(1,2,44100,8))
                self.assertEqual(struct.unpack('<8h',f.readframes(8)),(-32768,-32768,-16384,-1,0,16384,32767,32767))

    def test_runner_and_guard_fail_closed_contract(self):
        source=(ROOT/'phone/runner.cc').read_text()
        self.assertIn('session.disable_cpu_ep_fallback","1',source)
        self.assertNotIn('EnableProfiling',source)
        self.assertIn('wave.resize(r.L*HOP)',source)
        self.assertNotIn('wave.resize(r.predicted_frames)',source)
        self.assertIn('throw std::runtime_error("nonzero inactive latent; reject rather than repair")',source)
        self.assertIn('cached_t!=r.T',source)
        self.assertIn('first_native_wave_ready_from_entry_seconds',source)
        guard=(ROOT/'tools/run_phone.py').read_text()
        self.assertIn("PHONE_SLOT_SCHEDULED",guard)
        self.assertIn('fcntl.LOCK_EX|fcntl.LOCK_NB',guard)
        self.assertIn('guard.validate_snapshot',guard)
        self.assertIn('readlink /proc/$p/exe',guard)
        self.assertNotIn('am force-stop',guard)
        self.assertNotIn('adb kill-server',guard)
        self.assertNotIn('pm clear',guard)


if __name__ == '__main__':
    unittest.main()
