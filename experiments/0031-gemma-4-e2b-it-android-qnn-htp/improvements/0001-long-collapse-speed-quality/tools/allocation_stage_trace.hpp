#pragma once
// Fixed-stack/no-heap observer. No allocator replacement, no cap or model change.
#include <cerrno>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <fcntl.h>
#include <limits.h>
#include <pthread.h>
#include <sys/resource.h>
#include <time.h>
#include <unistd.h>

namespace gemma_alloc_trace {
struct State { pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER; int fd = -2; size_t bytes = 0; unsigned events = 0; };
inline State& state() noexcept { static State s; return s; }
inline bool product(size_t a, size_t b, size_t& result) noexcept {
  if (b && a > SIZE_MAX / b) { result = 0; return false; }
  result = a * b; return true;
}
inline size_t length(const char* s) noexcept { size_t n=0; while (s && s[n]) ++n; return n; }
struct Line {
  char data[1536]; size_t used=0;
  void text(const char* s) noexcept { for(size_t i=0;s && s[i] && used+1<sizeof(data);++i) data[used++]=s[i]; }
  void number(uint64_t value) noexcept { char digits[32]; size_t n=0; do { digits[n++]=char('0'+value%10);value/=10;} while(value && n<sizeof(digits)); while(n && used+1<sizeof(data))data[used++]=digits[--n]; }
  void field(const char* key,uint64_t value) noexcept { text(" ");text(key);text("=");number(value); }
};
inline bool write_all(int fd,const char* p,size_t size) noexcept {
  while(size) { ssize_t n=::write(fd,p,size);if(n<0 && errno==EINTR)continue;if(n<=0)return false;p+=n;size-=size_t(n); } return true;
}
inline bool decimal(const char* p,size_t n,uint64_t& value) noexcept {
  value=0;size_t i=0;while(i<n && (p[i]==' ' || p[i]=='\t'))++i;bool found=false;
  while(i<n && p[i]>='0' && p[i]<='9') { unsigned d=unsigned(p[i++]-'0');if(value>(UINT64_MAX-d)/10)return false;value=value*10+d;found=true; }return found;
}
inline bool matches(const char* p,size_t n,const char* key) noexcept { size_t k=length(key);if(n<k)return false;for(size_t i=0;i<k;++i)if(p[i]!=key[i])return false;return true; }
struct Memory { uint64_t peak=0,size=0,rss=0,available=0; unsigned valid=0; bool truncated=false; };
inline void read_memory_file(const char* path,Memory& m,bool system) noexcept {
  int fd=::open(path,O_RDONLY|O_CLOEXEC);if(fd<0)return;char buffer[8192];ssize_t used=::read(fd,buffer,sizeof(buffer));::close(fd);
  if(used<=0)return;if(size_t(used)==sizeof(buffer))m.truncated=true;
  for(size_t start=0;start<size_t(used);) {
    size_t end=start;while(end<size_t(used) && buffer[end]!='\n')++end;
    const char* keys[]={"VmPeak:","VmSize:","VmRSS:","MemAvailable:"};
    for(unsigned j=0;j<4;++j) {
      if((system && j!=3)||(!system && j==3))continue;
      if(matches(buffer+start,end-start,keys[j])) {uint64_t kb=0;size_t k=length(keys[j]);if(decimal(buffer+start+k,end-start-k,kb) && kb<=UINT64_MAX/1024) {uint64_t bytes=kb*1024;if(j==0)m.peak=bytes;else if(j==1)m.size=bytes;else if(j==2)m.rss=bytes;else m.available=bytes;m.valid|=(1u<<j);}}
    }
    start=end+1;
  }
}
inline void emit(const char* phase,const char* stage,size_t factor_a,size_t factor_b,size_t element_bytes,
                 size_t current_size,size_t current_capacity,int errno_at_observation) noexcept {
  const int saved_errno=errno;
  State& s=state();pthread_mutex_lock(&s.mutex);
  if(s.fd==-2) {
    const char* dir=::getenv("GEMMA_PREFILL_CAPTURE_DIR");int d=dir?::open(dir,O_RDONLY|O_DIRECTORY|O_CLOEXEC|O_NOFOLLOW):-1;
    s.fd=d>=0?::openat(d,"allocation-stages.log",O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC|O_NOFOLLOW,0600):-1;
    if(d>=0)::close(d);
  }
  if(s.fd>=0 && s.events<64 && s.bytes<65536) {
    Memory m;read_memory_file("/proc/self/status",m,false);read_memory_file("/proc/meminfo",m,true);
    rlimit limit{};bool limit_valid=::getrlimit(RLIMIT_AS,&limit)==0;timespec ts{};clock_gettime(CLOCK_MONOTONIC,&ts);
    size_t elements=0,bytes=0;bool elements_valid=product(factor_a,factor_b,elements);bool bytes_valid=elements_valid && product(elements,element_bytes,bytes);
    Line line;line.text("GEMMA_ALLOC_V1 phase=");line.text(phase);line.text(" stage=");line.text(stage);
    line.field("event",s.events);line.field("monotonic_ns",uint64_t(ts.tv_sec)*1000000000ULL+uint64_t(ts.tv_nsec));
    line.field("allocation_request",element_bytes!=0);line.field("factor_a",factor_a);line.field("factor_b",factor_b);line.field("element_bytes",element_bytes);
    line.field("requested_elements_valid",elements_valid);line.field("requested_elements",elements);
    line.field("requested_bytes_valid",bytes_valid);line.field("vector_requested_bytes",bytes);
    line.field("vector_size",current_size);line.field("vector_capacity",current_capacity);
    line.field("errno_at_observation",errno_at_observation<0?0:uint64_t(errno_at_observation));
    line.field("rlimit_valid",limit_valid);line.field("AS_soft",uint64_t(limit.rlim_cur));line.field("AS_hard",uint64_t(limit.rlim_max));
    line.field("AS_soft_unlimited",limit_valid && limit.rlim_cur==RLIM_INFINITY);line.field("AS_hard_unlimited",limit_valid && limit.rlim_max==RLIM_INFINITY);
    line.field("memory_valid_bits",m.valid);line.field("VmPeak",m.peak);line.field("VmSize",m.size);line.field("VmRSS",m.rss);line.field("MemAvailable",m.available);line.field("proc_read_truncated",m.truncated);line.text("\n");
    if(s.bytes+line.used<=65536 && write_all(s.fd,line.data,line.used) && ::fdatasync(s.fd)==0) {s.bytes+=line.used;++s.events;}
    else {::close(s.fd);s.fd=-1;static const char error[]="GEMMA_ALLOC_TRACE_ERROR bounded logger unavailable\n";write_all(2,error,sizeof(error)-1);}
  }
  pthread_mutex_unlock(&s.mutex);errno=saved_errno;
}

template<class V,class F> inline void resize(const char* name,V& v,size_t a,size_t b,F&& original) {
  emit("before",name,a,b,sizeof(typename V::value_type),v.size(),v.capacity(),errno);
  try { original(); }
  catch (...) { const int observed_errno=errno;emit("throw",name,a,b,sizeof(typename V::value_type),v.size(),v.capacity(),observed_errno);throw; }
  emit("after",name,a,b,sizeof(typename V::value_type),v.size(),v.capacity(),errno);
}
template<class F> inline auto construct(const char* name,size_t elements,size_t element_bytes,F&& original) -> decltype(original()) {
  emit("before",name,elements,1,element_bytes,0,0,errno);
  try {auto value=original();emit("after",name,elements,1,element_bytes,value.size(),value.capacity(),errno);return value;}
  catch (...) {const int observed_errno=errno;emit("throw",name,elements,1,element_bytes,0,0,observed_errno);throw;}
}
template<class F> inline bool call(const char* name,F&& original) {
  emit("before_call",name,0,0,0,0,0,errno);
  try {bool value=original();emit(value?"after_call_true":"after_call_false",name,0,0,0,0,0,errno);return value;}
  catch (...) {const int observed_errno=errno;emit("throw",name,0,0,0,0,0,observed_errno);throw;}
}
template<class F> inline auto scalar_call(const char* name,F&& original) -> decltype(original()) {
  emit("before_call",name,0,0,0,0,0,errno);
  try {auto value=original();emit("after_call",name,0,0,0,0,0,errno);return value;}
  catch (...) {const int observed_errno=errno;emit("throw",name,0,0,0,0,0,observed_errno);throw;}
}
} // namespace gemma_alloc_trace
