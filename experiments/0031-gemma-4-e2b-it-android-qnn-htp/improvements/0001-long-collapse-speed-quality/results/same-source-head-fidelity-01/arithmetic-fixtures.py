TOOLS='/home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/tools'
import sys,numpy as np
sys.path.insert(0,TOOLS)
import audit_same_source_head as a
assert a.unpack2(np.array([[228]],dtype=np.uint8)).tolist()==[[-2,-1,0,1]]
v=np.array([0x3f808000,0x3f818000],dtype=np.uint32).view(np.float32)
assert a.bf16_round(v).view(np.uint32).tolist()==[0x3f800000,0x3f820000]
x=a.candidates(np.array([[228]],dtype=np.uint8),np.array([[2]],dtype=np.float32))
assert x['f32'].tolist()==[[-4.0,-2.0,0.0,2.0]]
assert np.array_equal(x['f32'],x['bf16_forward'])
print('3 tiny arithmetic fixtures passed; no model forward')
