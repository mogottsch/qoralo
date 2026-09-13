#include "MmappedFile/MmappedFile.hpp"
#ifdef WITH_OBSERVER
#include "qualla/mapping_stage_trace.hpp"
#endif
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <fcntl.h>
#include <new>
#include <sys/mman.h>
#include <unistd.h>

static bool fail_mapping=false, forbid_heap=false;
static unsigned mapping_calls=0;
extern "C" void* __real_mmap(void*,size_t,int,int,int,off_t);
extern "C" void* __wrap_mmap(void* p,size_t n,int prot,int flags,int fd,off_t off){
 ++mapping_calls;if(fail_mapping){errno=ENOMEM;return MAP_FAILED;}return __real_mmap(p,n,prot,flags,fd,off);
}
extern "C" void* __real_malloc(size_t);
extern "C" void* __real_calloc(size_t,size_t);
extern "C" void* __real_realloc(void*,size_t);
extern "C" void* __wrap_malloc(size_t n){if(forbid_heap)_exit(91);return __real_malloc(n);}
extern "C" void* __wrap_calloc(size_t a,size_t b){if(forbid_heap)_exit(92);return __real_calloc(a,b);}
extern "C" void* __wrap_realloc(void* p,size_t n){if(forbid_heap)_exit(93);return __real_realloc(p,n);}
void* operator new(size_t n){if(forbid_heap)_exit(94);void*p=__real_malloc(n);if(!p)throw std::bad_alloc();return p;}
void operator delete(void*p) noexcept{free(p);}
void operator delete(void*p,size_t) noexcept{free(p);}

int main(int argc,char**argv){
 fail_mapping=argv[3][0]=='1';setenv("GEMMA_PREFILL_CAPTURE_DIR",argv[2],1);
#ifdef WITH_OBSERVER
 if(gemma_mapping_trace::role("unrelated_embedding_int8_lut.bin")!=nullptr)return 10;
 errno=E2BIG;forbid_heap=true;
 gemma_mapping_trace::emit("main","fixed_stack_test",true,4096,false,nullptr,0,false,false,false,false,0,errno);
 forbid_heap=false;if(errno!=E2BIG)return 11;
#endif
 mmapped::File file(argv[1]);
 bool before_open=file.isOpen();bool before_null=file.mutableData()==nullptr;uint64_t before_size=file.size();
 bool returned=file.remap(false); // public API returns the original private File::open result
 bool after_open=file.isOpen();bool after_null=file.mutableData()==nullptr;uint64_t after_size=file.size();
 if(mapping_calls!=2)return 12;
 if(fail_mapping){if(!returned || before_open || after_open || !before_null || !after_null || before_size || after_size)return 13;}
 else {if(!returned || !before_open || !after_open || before_null || after_null || before_size!=4096 || after_size!=4096)return 14;}
#ifdef WITH_OBSERVER
 gemma_mapping_trace::emit("main","lut.cached",true,4096,true,file.mutableData(),file.size(),false,false,true,file.isOpen(),4096,errno);
 if((fcntl(gemma_mapping_trace::state().fd,F_GETFD)&FD_CLOEXEC)==0)return 15;
 forbid_heap=true;for(unsigned i=0;i<50;++i)gemma_mapping_trace::emit("main","cap",false,0,false,nullptr,0,false,false,false,false,0,errno);forbid_heap=false;
 if(gemma_mapping_trace::state().events>32 || gemma_mapping_trace::state().bytes>32768)return 16;
#endif
 printf("injected_failure=%u mmap_calls=%u remap_open_return=%u isOpen=%u pointer_null=%u mapped_bytes=%llu\n",fail_mapping,mapping_calls,returned,after_open,after_null,(unsigned long long)after_size);
 return 0;
}
