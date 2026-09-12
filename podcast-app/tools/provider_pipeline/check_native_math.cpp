#include "provider_math.h"
#include <fstream>
#include <cassert>
int main(int argc,char** argv) {
  assert(argc==2);provider::Gaussian rng; rng.reset();
  std::ofstream out(argv[1],std::ios::binary);
  for(int i=0;i<15*144*1000;++i) {const float value=rng.next();out.write(reinterpret_cast<const char*>(&value),4);}
  assert(rng.count()==15*144*1000);out.close();assert(out);
  for(int n=1;n<=320;++n) for(int prefix: {0,1}) for(int r: {2,4,8}) {
    const auto got=provider::edges(n+prefix,320+prefix,r);
    for(int i=0;i<n+prefix+2*r;++i) assert(got[i]==std::clamp(i-r,0,n+prefix-1));
  }
  for(int n=1;n<=512;++n) for(int r: {2,4,8,16}) {
    const auto got=provider::edges(n,512,r);
    for(int i=0;i<n+2*r;++i) assert(got[i]==std::clamp(i-r,0,n-1));
  }
  assert(provider::pcm16(1.f)==32767);assert(provider::pcm16(-1.f)==-32768);
  assert(provider::pcm16(0.5f)==16384);assert(provider::pcm16(-0.00001f)==-1);
}
