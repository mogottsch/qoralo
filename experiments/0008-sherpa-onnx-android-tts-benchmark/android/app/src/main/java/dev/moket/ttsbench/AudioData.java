package dev.moket.ttsbench;

public record AudioData(float[] samples, int sampleRate) {
    public AudioData { if(samples==null)throw new NullPointerException("samples"); if(sampleRate<=0)throw new IllegalArgumentException("sampleRate"); }
    public double durationSeconds(){ return samples.length/(double)sampleRate; }
}
