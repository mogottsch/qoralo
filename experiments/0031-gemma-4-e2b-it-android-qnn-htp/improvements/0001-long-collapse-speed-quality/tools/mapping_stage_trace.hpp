#pragma once
// Read-only mapping observations. Existing mapping/return behavior is not repaired.
#include "allocation_stage_trace.hpp"
#include <sys/mman.h>

namespace gemma_mapping_trace {
using gemma_alloc_trace::Line;
using gemma_alloc_trace::Memory;
using gemma_alloc_trace::read_memory_file;
using gemma_alloc_trace::write_all;
inline bool ends(const char* text,const char* suffix) noexcept {
  size_t n=gemma_alloc_trace::length(text),k=gemma_alloc_trace::length(suffix);
  if(n<k)return false;for(size_t i=0;i<k;++i)if(text[n-k+i]!=suffix[i])return false;return true;
}
inline const char* role(const char* name) noexcept {
  if(!name)return nullptr;const char* base=name;
  for(const char* p=name;*p;++p)if(*p=='/')base=p+1;
  size_t n=gemma_alloc_trace::length(base);
  if(n==gemma_alloc_trace::length("embedding_int8_lut.bin") && ends(base,"embedding_int8_lut.bin"))return "main";
  if(n==gemma_alloc_trace::length("embed_tokens_per_layer_int8_lut.bin") && ends(base,"embed_tokens_per_layer_int8_lut.bin"))return "ple";
  return nullptr;
}
struct State { pthread_mutex_t mutex=PTHREAD_MUTEX_INITIALIZER;int fd=-2;unsigned events=0;size_t bytes=0; };
inline State& state() noexcept {static State value;return value;}
inline void emit(const char* which,const char* phase,bool request_known,uint64_t requested,
                 bool address_known,const void* address,uint64_t mapped_bytes,
                 bool open_return_known,bool open_return,bool is_open_known,bool is_open,
                 uint64_t declared_lut_bytes,int errno_at_observation) noexcept {
  if(!which)return;
  const int saved_errno=errno;State& s=state();pthread_mutex_lock(&s.mutex);
  if(s.fd==-2) {
    const char* path=::getenv("GEMMA_PREFILL_CAPTURE_DIR");
    int dir=path?::open(path,O_RDONLY|O_DIRECTORY|O_CLOEXEC|O_NOFOLLOW):-1;
    s.fd=dir>=0?::openat(dir,"mapping-stages.log",O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC|O_NOFOLLOW,0600):-1;
    if(dir>=0)::close(dir);
    if(path && s.fd<0){static const char error[]="GEMMA_MAPPING_TRACE_ERROR open failed\n";write_all(2,error,sizeof(error)-1);}
  }
  if(s.fd>=0 && s.events<32 && s.bytes<32768) {
    Memory mem;read_memory_file("/proc/self/status",mem,false);read_memory_file("/proc/meminfo",mem,true);
    rlimit limit{};bool valid=::getrlimit(RLIMIT_AS,&limit)==0;timespec stamp{};clock_gettime(CLOCK_MONOTONIC,&stamp);
    Line line;line.text("GEMMA_MAPPING_V1 role=");line.text(which);line.text(" phase=");line.text(phase);
    line.field("event",s.events);line.field("monotonic_ns",uint64_t(stamp.tv_sec)*1000000000ULL+uint64_t(stamp.tv_nsec));
    line.field("request_known",request_known);line.field("requested_file_bytes",requested);
    line.field("length_fits_size_t",requested<=SIZE_MAX);line.field("syscall_length_bytes",uint64_t(static_cast<size_t>(requested)));
    line.field("address_known",address_known);line.field("address",uint64_t(reinterpret_cast<uintptr_t>(address)));
    line.field("address_is_MAP_FAILED",address_known && address==MAP_FAILED);line.field("pointer_nonnull",address_known && address!=nullptr);
    line.field("mapped_bytes",mapped_bytes);line.field("File_open_return_known",open_return_known);line.field("File_open_return",open_return);
    line.field("isOpen_known",is_open_known);line.field("isOpen",is_open);line.field("declared_lut_bytes",declared_lut_bytes);
    line.field("errno_at_observation",errno_at_observation<0?0:uint64_t(errno_at_observation));
    line.field("rlimit_valid",valid);line.field("AS_soft",uint64_t(limit.rlim_cur));line.field("AS_hard",uint64_t(limit.rlim_max));
    line.field("AS_soft_unlimited",valid && limit.rlim_cur==RLIM_INFINITY);line.field("memory_valid_bits",mem.valid);
    line.field("VmPeak",mem.peak);line.field("VmSize",mem.size);line.field("VmRSS",mem.rss);line.field("MemAvailable",mem.available);
    line.field("proc_read_truncated",mem.truncated);line.text("\n");
    if(s.bytes+line.used<=32768 && write_all(s.fd,line.data,line.used) && ::fdatasync(s.fd)==0){s.bytes+=line.used;++s.events;}
    else {::close(s.fd);s.fd=-1;static const char error[]="GEMMA_MAPPING_TRACE_ERROR write failed\n";write_all(2,error,sizeof(error)-1);}
  }
  pthread_mutex_unlock(&s.mutex);errno=saved_errno;
}
} // namespace gemma_mapping_trace
