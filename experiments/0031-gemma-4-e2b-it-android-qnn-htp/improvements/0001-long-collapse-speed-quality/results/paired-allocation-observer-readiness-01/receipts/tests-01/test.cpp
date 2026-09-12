#include "allocation_stage_trace.hpp"
#include <new>
#include <vector>
#include <cerrno>
#include <cstdint>
#include <unistd.h>

static bool forbid_heap=false;
extern "C" void* __real_malloc(size_t);
extern "C" void* __real_calloc(size_t,size_t);
extern "C" void* __real_realloc(void*,size_t);
extern "C" void* __wrap_malloc(size_t n){if(forbid_heap)_exit(91);return __real_malloc(n);}
extern "C" void* __wrap_calloc(size_t a,size_t b){if(forbid_heap)_exit(92);return __real_calloc(a,b);}
extern "C" void* __wrap_realloc(void* p,size_t n){if(forbid_heap)_exit(93);return __real_realloc(p,n);}
void* operator new(size_t n){if(forbid_heap)_exit(94);void*p=__real_malloc(n);if(!p)throw std::bad_alloc();return p;}
void operator delete(void*p) noexcept{free(p);}
void operator delete(void*p,size_t) noexcept{free(p);}
struct OriginalError {int id;};
int main(int argc,char**argv){
 setenv("GEMMA_PREFILL_CAPTURE_DIR",argv[1],1);
 errno=E2BIG;forbid_heap=true;
 gemma_alloc_trace::emit("test","fixed_stack",3,4,2,5,6,errno);
 forbid_heap=false;if(errno!=E2BIG)return 2;
 std::vector<uint8_t> v{1,2,3};int calls=0;
 gemma_alloc_trace::resize("test.resize",v,6,1,[&](){++calls;v.resize(6);});
 if(calls!=1 || v.size()!=6 || v[0]!=1)return 3;
 try {gemma_alloc_trace::resize("test.failure",v,SIZE_MAX,2,[&](){++calls;errno=ENOSPC;throw OriginalError{77};});return 4;}
 catch(const OriginalError&e){if(e.id!=77 || calls!=2 || errno!=ENOSPC)return 5;}
 size_t value=9;if(gemma_alloc_trace::product(SIZE_MAX,2,value) || value!=0)return 6;
 int ctor=0;auto w=gemma_alloc_trace::construct("test.construct",4,1,[&](){++ctor;return std::vector<uint8_t>(4,7);});
 if(ctor!=1 || w.size()!=4 || w[2]!=7)return 7;
 size_t scalar=gemma_alloc_trace::scalar_call("test.scalar",[](){return size_t(1929);});if(scalar!=1929)return 8;
 if(!gemma_alloc_trace::call("test.bool",[](){return true;}))return 9;
 if((fcntl(gemma_alloc_trace::state().fd,F_GETFD)&FD_CLOEXEC)==0)return 10;
 forbid_heap=true;for(unsigned n=0;n<100;++n)gemma_alloc_trace::emit("test","cap",1,1,1,0,0,0);forbid_heap=false;
 if(gemma_alloc_trace::state().events>64 || gemma_alloc_trace::state().bytes>65536)return 11;
 return 0;
}
