#include "prefill_capture.hpp"
#include <array>
int main(int argc,char**argv){
 setenv("GEMMA_PREFILL_CAPTURE_DIR",argv[1],1);
 std::array<uint16_t,4> values{0,32768,65535,17}, before=values;
 gemma_prefill_capture::save("input",0,"inputs_embeds",values.data(),sizeof(values),{{"shape",{1,4}},{"cache_tensor",false}});
 auto& s=gemma_prefill_capture::state();
 if(s.captures!=1 || (fcntl(s.journal,F_GETFD)&FD_CLOEXEC)==0 || values!=before)return 2;
 // Duplicate capture must fail only observation, not alter the original buffer.
 gemma_prefill_capture::save("input",0,"inputs_embeds",values.data(),sizeof(values),{{"shape",{1,4}}});
 if(!s.disabled || values!=before)return 3;
 return 0;
}
