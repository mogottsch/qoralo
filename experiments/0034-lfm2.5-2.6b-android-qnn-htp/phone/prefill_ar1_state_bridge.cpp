#include <algorithm>
#include <array>
#include <cstdio>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
namespace fs=std::filesystem;
static constexpr size_t H=2048,CAP=4096,PREFILL=171,AR1_CACHE=4095;
static const std::array<int,8> ATTN={2,5,9,13,17,21,24,27};
static bool attention(int x){for(int y:ATTN)if(x==y)return true;return false;}
static std::vector<float> readf(const fs::path&p,size_t count){std::ifstream f(p,std::ios::binary|std::ios::ate);if(!f||size_t(f.tellg())!=count*4)throw std::runtime_error("input size: "+p.string());f.seekg(0);std::vector<float>x(count);f.read(reinterpret_cast<char*>(x.data()),count*4);return x;}
static void writef(const fs::path&p,const std::vector<float>&x){std::ofstream f(p,std::ios::binary);if(!f)throw std::runtime_error("output: "+p.string());f.write(reinterpret_cast<const char*>(x.data()),x.size()*4);}
int main(int argc,char**argv){try{if(argc!=4)throw std::runtime_error("usage: bridge PREFILL_RESULT EMBEDDING597 OUT");fs::path src=argv[1],embed=argv[2],out=argv[3];fs::create_directories(out);std::ofstream list(out/"input-list.txt");auto entry=[&](const std::string&n,const fs::path&p){list<<n<<":="<<p.string()<<" ";};fs::copy_file(embed,out/"00-embedding.raw",fs::copy_options::overwrite_existing);entry("/model/embed_tokens/GatherBlockQuantized/output_0",out/"00-embedding.raw");float pos=171.0f;{std::ofstream f(out/"01-position.raw",std::ios::binary);f.write(reinterpret_cast<char*>(&pos),4);}entry("position_ids",out/"01-position.raw");std::vector<float>mask(CAP,-65504.f);for(size_t i=0;i<PREFILL;i++)mask[i]=0;mask.back()=0;writef(out/"02-mask.raw",mask);entry("attention_mask",out/"02-mask.raw");int file=3;
for(int layer=0;layer<30;layer++){auto path=[&](const std::string&s){char n[32];std::snprintf(n,sizeof(n),"%02d-%s.raw",file++,s.c_str());return out/n;};if(attention(layer)){for(bool key:{true,false}){std::string base="present_"+std::to_string(layer)+(key?"_key.raw":"_value.raw");auto x=readf(src/base,8*PREFILL*64);std::vector<float>y(8*AR1_CACHE*64,0.f);if(key){for(size_t row=0;row<8*64;row++)std::copy_n(x.data()+row*PREFILL,PREFILL,y.data()+row*AR1_CACHE);}else{for(size_t head=0;head<8;head++)std::copy_n(x.data()+head*PREFILL*64,PREFILL*64,y.data()+head*AR1_CACHE*64);}auto p=path("state");writef(p,y);entry("past_key_values."+std::to_string(layer)+(key?".key":".value"),p);}}else{std::string base="present_conv_"+std::to_string(layer)+".raw";auto x=readf(src/base,H*3);auto p=path("conv");writef(p,x);entry("past_conv."+std::to_string(layer),p);}}
list<<"\n";list.close();return 0;}catch(const std::exception&e){std::cerr<<"fatal="<<e.what()<<"\n";return 1;}}
