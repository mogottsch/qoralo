package dev.moket.ttsbench;

import java.util.*;

public record BenchmarkResult(long loadNanos, MemoryMetrics loadMemory, List<Run> runs, Double warmMedianRtf, Failure failure) {
    public record Run(String state,long synthesisNanos,long firstCallbackNanos,String callbackUnavailableReason,
            int sampleCount,int sampleRate,double durationSeconds,double rtf,String wavPath,String wavSha256,
            AudioValidation validation,MemoryMetrics memory) {}
    public record Failure(String stage,String code,String message,String exceptionType) {}

    public static double median(List<Double> values){
        if(values.isEmpty())throw new IllegalArgumentException("empty median");
        double[] a=values.stream().mapToDouble(Double::doubleValue).sorted().toArray();int n=a.length;
        return n%2==1?a[n/2]:(a[n/2-1]+a[n/2])/2;
    }

    public String toJson(){
        StringBuilder b=new StringBuilder("{\"load_nanos\":").append(loadNanos).append(",\"load_memory\":");
        appendMemory(b,loadMemory);
        b.append(",\"warm_median_rtf\":").append(warmMedianRtf==null?"null":warmMedianRtf).append(",\"runs\":[");
        for(int i=0;i<runs.size();i++){
            Run r=runs.get(i);AudioValidation v=r.validation;if(i>0)b.append(',');
            b.append("{\"state\":\"").append(escape(r.state)).append("\",\"synthesis_nanos\":").append(r.synthesisNanos)
             .append(",\"first_callback_nanos\":").append(r.firstCallbackNanos<0?"null":r.firstCallbackNanos)
             .append(",\"callback_unavailable_reason\":").append(r.callbackUnavailableReason==null?"null":"\""+escape(r.callbackUnavailableReason)+"\"")
             .append(",\"sample_count\":").append(r.sampleCount).append(",\"sample_rate\":").append(r.sampleRate)
             .append(",\"duration_seconds\":").append(r.durationSeconds).append(",\"rtf\":").append(r.rtf)
             .append(",\"wav_path\":\"").append(escape(r.wavPath)).append("\",\"wav_sha256\":\"").append(r.wavSha256)
             .append("\",\"audio_validation\":{\"valid\":").append(v.valid()).append(",\"silent\":").append(v.silent()).append(",\"clipped\":").append(v.clipped()).append(",\"peak\":").append(v.peak()).append('}')
             .append(",\"memory\":");
            appendMemory(b,r.memory);b.append('}');
        }
        b.append(']');
        if(failure!=null)b.append(",\"failure\":{\"stage\":\"").append(escape(failure.stage)).append("\",\"code\":\"").append(escape(failure.code)).append("\",\"message\":\"").append(escape(failure.message)).append("\",\"exception_type\":\"").append(escape(failure.exceptionType)).append("\"}");
        return b.append('}').toString();
    }

    private static void appendMemory(StringBuilder b,MemoryMetrics m){
        if(m==null){b.append("null");return;}
        b.append("{\"pss_bytes\":").append(m.pssBytes()).append(",\"rss_bytes\":").append(m.rssBytes()).append(",\"vm_hwm_bytes\":").append(m.vmHwmBytes())
         .append(",\"vm_hwm_semantics\":\"").append(m.vmHwmSemantics()).append("\",\"sampled_phase\":\"").append(escape(m.phase())).append("\",\"sampled_peak_pss_bytes\":").append(m.sampledPeakPssBytes()).append(",\"sampled_peak_rss_bytes\":").append(m.sampledPeakRssBytes()).append('}');
    }

    private static String escape(String s){
        StringBuilder out=new StringBuilder();
        for(int i=0;i<s.length();i++){char c=s.charAt(i);switch(c){case '"'->out.append("\\\"");case '\\'->out.append("\\\\");case '\b'->out.append("\\b");case '\f'->out.append("\\f");case '\n'->out.append("\\n");case '\r'->out.append("\\r");case '\t'->out.append("\\t");default->{if(c<0x20)out.append(String.format("\\u%04x",(int)c));else out.append(c);}}}
        return out.toString();
    }
}
