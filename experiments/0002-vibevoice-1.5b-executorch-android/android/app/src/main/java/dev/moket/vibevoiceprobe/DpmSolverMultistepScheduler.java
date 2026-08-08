package dev.moket.vibevoiceprobe;

/** Fixed FP32 DPM-Solver++ order-two midpoint update used by VibeVoice. */
final class DpmSolverMultistepScheduler {
    private final float[] sigmas;
    private int stepIndex;
    private float[] previousX0;

    DpmSolverMultistepScheduler(float[] sigmas) {
        if (sigmas.length != 11 || sigmas[sigmas.length - 1] != 0.0f) {
            throw new IllegalArgumentException("Expected the locked eleven-sigma schedule ending in zero");
        }
        this.sigmas = sigmas.clone();
    }

    float[] step(float[] prediction, float[] sample) {
        if (prediction.length != sample.length || stepIndex >= sigmas.length - 1) {
            throw new IllegalArgumentException("Invalid diffusion scheduler input");
        }
        Scalars source = Scalars.fromSigma(sigmas[stepIndex]);
        Scalars target = Scalars.fromSigma(sigmas[stepIndex + 1]);
        float h = target.lambda - source.lambda;
        float coefficient = target.alpha * ((float) Math.exp(-h) - 1.0f);
        float ratio = target.sigma / source.sigma;

        float[] currentX0 = new float[sample.length];
        float[] result = new float[sample.length];
        boolean firstOrder = previousX0 == null || stepIndex == sigmas.length - 2;
        float inverseR0 = 0.0f;
        if (!firstOrder) {
            Scalars previous = Scalars.fromSigma(sigmas[stepIndex - 1]);
            float r0 = (source.lambda - previous.lambda) / h;
            inverseR0 = 1.0f / r0;
        }
        for (int index = 0; index < sample.length; index++) {
            currentX0[index] = source.alpha * sample[index] - source.sigma * prediction[index];
            float value = ratio * sample[index] - coefficient * currentX0[index];
            if (!firstOrder) {
                float derivative = inverseR0 * (currentX0[index] - previousX0[index]);
                value -= 0.5f * coefficient * derivative;
            }
            result[index] = value;
        }
        previousX0 = currentX0;
        stepIndex++;
        return result;
    }

    private static final class Scalars {
        final float alpha;
        final float sigma;
        final float lambda;

        private Scalars(float alpha, float sigma, float lambda) {
            this.alpha = alpha;
            this.sigma = sigma;
            this.lambda = lambda;
        }

        static Scalars fromSigma(float rawSigma) {
            float alpha = 1.0f / (float) Math.sqrt(rawSigma * rawSigma + 1.0f);
            float sigma = rawSigma * alpha;
            float lambda = (float) Math.log(alpha) - (float) Math.log(sigma);
            return new Scalars(alpha, sigma, lambda);
        }
    }
}
