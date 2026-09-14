// Authored HOST-ONLY QnnCpu scalar fixtures. No model/DLC/HTP/phone inputs.
#include <QnnInterface.h>
#include <QnnOpDef.h>
#include <dlfcn.h>
#include <cmath>
#include <cstdio>
#include <cstdint>
#include <limits>

static bool report(const char* name,const char* stage,Qnn_ErrorHandle_t code){
  std::printf("{\"case\":\"%s\",\"event\":\"api\",\"stage\":\"%s\",\"status\":%llu}\n",name,stage,(unsigned long long)code);std::fflush(stdout);return code==QNN_SUCCESS;
}
static Qnn_Tensor_t tensor(const char* name,Qnn_TensorType_t type,Qnn_DataType_t dtype,uint32_t* dims,void* data,uint32_t bytes,float scale=0,int32_t offset=0){
  Qnn_Tensor_t t=QNN_TENSOR_INIT;t.v1.name=name;t.v1.type=type;t.v1.dataFormat=QNN_TENSOR_DATA_FORMAT_FLAT_BUFFER;t.v1.dataType=dtype;
  t.v1.rank=1;t.v1.dimensions=dims;t.v1.memType=QNN_TENSORMEMTYPE_RAW;t.v1.clientBuf=type==QNN_TENSOR_TYPE_STATIC?Qnn_ClientBuffer_t{data,bytes}:Qnn_ClientBuffer_t{nullptr,0};
  if(dtype==QNN_DATATYPE_UFIXED_POINT_16){t.v1.quantizeParams.encodingDefinition=QNN_DEFINITION_DEFINED;t.v1.quantizeParams.quantizationEncoding=QNN_QUANTIZATION_ENCODING_SCALE_OFFSET;t.v1.quantizeParams.scaleOffsetEncoding={scale,offset};}
  return t;
}
static bool run_case(QNN_INTERFACE_VER_TYPE& api,Qnn_BackendHandle_t backend,int mode){
  const char* names[]={"direct_UF16_Power","F32_Power","F32_Power_then_Convert","F32_specials_Convert"};const char* name=names[mode];Qnn_ContextHandle_t context=nullptr;Qnn_GraphHandle_t graph=nullptr;
  if(!report(name,"contextCreate",api.contextCreate(backend,nullptr,nullptr,&context)))return false;
  auto finish=[&](bool ok){report(name,"contextFree",api.contextFree(context,nullptr));return ok;};
  if(!report(name,"graphCreate",api.graphCreate(context,name,nullptr,&graph)))return finish(false);
  uint32_t four=4,one=1;uint16_t input_words[4]={0,1,2,65535},exponent_word=0,output_words[4]={0xcafe,0xcafe,0xcafe,0xcafe};
  const float input_scale=0.023287702351808548f,output_scale=0.00010432041017338634f,exponent_scale=7.629510946571827e-06f;
  float input_float[4]={0,input_scale,2*input_scale,65535*input_scale};float exponent_float=-0.5f;float output_float[4]={NAN,NAN,NAN,NAN};
  if(mode==3){input_float[0]=INFINITY;input_float[1]=-INFINITY;input_float[2]=NAN;input_float[3]=.1f;}
  auto input=tensor("input",QNN_TENSOR_TYPE_APP_WRITE,mode==0?QNN_DATATYPE_UFIXED_POINT_16:QNN_DATATYPE_FLOAT_32,&four,mode==0?(void*)input_words:(void*)input_float,mode==0?sizeof(input_words):sizeof(input_float),input_scale,0);
  auto output=tensor("output",QNN_TENSOR_TYPE_APP_READ,mode==1?QNN_DATATYPE_FLOAT_32:QNN_DATATYPE_UFIXED_POINT_16,&four,mode==1?(void*)output_float:(void*)output_words,mode==1?sizeof(output_float):sizeof(output_words),output_scale,0);
  if(!report(name,"createInput",api.tensorCreateGraphTensor(graph,&input))||!report(name,"createOutput",api.tensorCreateGraphTensor(graph,&output)))return finish(false);
  Qnn_Tensor_t exponent=QNN_TENSOR_INIT,intermediate=QNN_TENSOR_INIT;
  if(mode!=3){
    exponent=tensor("exponent",QNN_TENSOR_TYPE_STATIC,mode==0?QNN_DATATYPE_UFIXED_POINT_16:QNN_DATATYPE_FLOAT_32,&one,mode==0?(void*)&exponent_word:(void*)&exponent_float,mode==0?sizeof(exponent_word):sizeof(exponent_float),exponent_scale,-65535);
    if(!report(name,"createExponent",api.tensorCreateGraphTensor(graph,&exponent)))return finish(false);
    if(mode==2){intermediate=tensor("power_value",QNN_TENSOR_TYPE_NATIVE,QNN_DATATYPE_FLOAT_32,&four,nullptr,0);if(!report(name,"createIntermediate",api.tensorCreateGraphTensor(graph,&intermediate)))return finish(false);}
    Qnn_Param_t parameter=QNN_PARAM_INIT;parameter.name=QNN_OP_ELEMENT_WISE_BINARY_PARAM_OPERATION;parameter.paramType=QNN_PARAMTYPE_SCALAR;parameter.scalarParam.dataType=QNN_DATATYPE_UINT_32;parameter.scalarParam.uint32Value=QNN_OP_ELEMENT_WISE_BINARY_OPERATION_POWER;
    Qnn_Tensor_t inputs[2]={input,exponent};Qnn_Tensor_t outputs[1]={mode==2?intermediate:output};Qnn_OpConfig_t op=QNN_OPCONFIG_INIT;op.v1.name="power";op.v1.packageName="qti.aisw";op.v1.typeName=QNN_OP_ELEMENT_WISE_BINARY;op.v1.numOfParams=1;op.v1.params=&parameter;op.v1.numOfInputs=2;op.v1.inputTensors=inputs;op.v1.numOfOutputs=1;op.v1.outputTensors=outputs;
    if(!report(name,"addPower",api.graphAddNode(graph,op)))return finish(false);
  }
  if(mode>=2){
    Qnn_Tensor_t inputs[1]={mode==2?intermediate:input};Qnn_Tensor_t outputs[1]={output};Qnn_OpConfig_t op=QNN_OPCONFIG_INIT;op.v1.name="convert";op.v1.packageName="qti.aisw";op.v1.typeName=QNN_OP_CONVERT;op.v1.numOfInputs=1;op.v1.inputTensors=inputs;op.v1.numOfOutputs=1;op.v1.outputTensors=outputs;
    if(!report(name,"addConvert",api.graphAddNode(graph,op)))return finish(false);
  }
  if(!report(name,"finalize",api.graphFinalize(graph,nullptr,nullptr)))return finish(false);
  // Non-static tensor buffers are attached for execution, not tensor creation.
  input.v1.clientBuf={mode==0?(void*)input_words:(void*)input_float,mode==0?uint32_t(sizeof(input_words)):uint32_t(sizeof(input_float))};
  output.v1.clientBuf={mode==1?(void*)output_float:(void*)output_words,mode==1?uint32_t(sizeof(output_float)):uint32_t(sizeof(output_words))};
  if(!report(name,"execute",api.graphExecute(graph,&input,1,&output,1,nullptr,nullptr)))return finish(false);
  if(mode==1){
    std::printf("{\"case\":\"%s\",\"event\":\"output\",\"dtype\":\"Float32\",\"values\":[",name);
    for(int i=0;i<4;++i){if(i)std::printf(",");if(std::isnan(output_float[i]))std::printf("\"NaN\"");else if(std::isinf(output_float[i]))std::printf(output_float[i]>0?"\"+Inf\"":"\"-Inf\"");else std::printf("%.9g",output_float[i]);}
    std::printf("]}\n");
  }else std::printf("{\"case\":\"%s\",\"event\":\"output\",\"dtype\":\"UF16\",\"codes\":[%u,%u,%u,%u],\"scale\":%.17g,\"offset\":0}\n",name,output_words[0],output_words[1],output_words[2],output_words[3],double(output_scale));
  std::fflush(stdout);return finish(true);
}
int main(int argc,char**argv){
  if(argc!=2)return 2;void* lib=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);if(!lib){std::fprintf(stderr,"dlopen failed: %s\n",dlerror());return 3;}
  using Getter=Qnn_ErrorHandle_t(*)(const QnnInterface_t***,uint32_t*);auto get=reinterpret_cast<Getter>(dlsym(lib,"QnnInterface_getProviders"));if(!get)return 4;
  const QnnInterface_t** providers=nullptr;uint32_t count=0;if(!report("harness","providers",get(&providers,&count)))return 5;
  const QnnInterface_t* chosen=nullptr;for(uint32_t i=0;i<count;++i)if(providers[i]->apiVersion.coreApiVersion.major==QNN_API_VERSION_MAJOR&&providers[i]->apiVersion.coreApiVersion.minor>=QNN_API_VERSION_MINOR){chosen=providers[i];break;}
  if(!chosen){std::fprintf(stderr,"no compatible installed CPU provider\n");return 6;}
  auto api=chosen->QNN_INTERFACE_VER_NAME;std::printf("{\"case\":\"harness\",\"event\":\"provider\",\"backend_id\":%u,\"core_major\":%u,\"core_minor\":%u}\n",chosen->backendId,chosen->apiVersion.coreApiVersion.major,chosen->apiVersion.coreApiVersion.minor);
  Qnn_BackendHandle_t backend=nullptr;if(!report("harness","backendCreate",api.backendCreate(nullptr,nullptr,&backend)))return 7;
  unsigned success=0;for(int i=0;i<4;++i)success+=run_case(api,backend,i);
  report("harness","backendFree",api.backendFree(backend));std::printf("{\"event\":\"harness_complete\",\"successful_cases\":%u,\"cases\":4,\"full_model_or_phone_executed\":false}\n",success);dlclose(lib);return 0;
}
