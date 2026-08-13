package dev.moket.ttsbench;

public record AudioValidation(boolean valid, boolean silent, boolean clipped, String reason, float peak) {
    public static AudioValidation inspect(AudioData audio) {
        if(audio.samples().length==0)return new AudioValidation(false,true,false,"empty_audio",0);
        double energy=0; float peak=0;
        for(float x:audio.samples()) { if(!Float.isFinite(x))return new AudioValidation(false,false,false,"non_finite_sample",peak); float a=Math.abs(x);peak=Math.max(peak,a);energy+=x*x; }
        boolean silent=Math.sqrt(energy/audio.samples().length)<1e-5;
        boolean clipped=peak>=1.0f;
        return new AudioValidation(!silent&&!clipped,silent,clipped,silent?"silence":clipped?"clipping":null,peak);
    }
}
