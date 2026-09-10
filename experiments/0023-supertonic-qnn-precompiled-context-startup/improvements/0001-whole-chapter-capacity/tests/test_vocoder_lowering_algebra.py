"""Synthetic NumPy algebra only. No learned weights, ONNX mutation or runtime."""
import unittest
import numpy as np


def conv(z,w,b,dilation):
    """Reference grouped depthwise valid cross-correlation; bias once, last."""
    batch,channels,length=z.shape;kernel=w.shape[1];outlen=length-dilation*(kernel-1)
    out=np.zeros((batch,channels,outlen),dtype=z.dtype)
    for k in range(kernel):out+=z[:,:,dilation*k:dilation*k+outlen]*w[None,:,k,None]
    return out+b[None,:,None]


def parity_batch1(z,w,b):
    even=conv(z[:,:,0::2],w,b,1);odd=conv(z[:,:,1::2],w,b,1)
    return np.stack((even,odd),axis=-1).reshape(z.shape[0],z.shape[1],-1)


def parity_batch2(z,w,b):
    batch,channels,length=z.shape
    phases=z.reshape(batch,channels,length//2,2).transpose(0,3,1,2).reshape(batch*2,channels,length//2)
    y=conv(phases,w,b,1)
    return y.reshape(batch,2,channels,y.shape[-1]).transpose(0,2,3,1).reshape(batch,channels,-1)


def zero_expanded(z,w,b):
    kernel=np.zeros((w.shape[0],2*w.shape[1]-1),dtype=w.dtype);kernel[:,::2]=w
    return conv(z,kernel,b,1)


def shifted_terms(z,w,b):
    length=z.shape[-1]-12
    terms=[z[:,:,2*k:2*k+length]*w[None,:,k,None] for k in range(7)]
    out=np.zeros_like(terms[0])
    for term in terms:out+=term
    return out+b[None,:,None]


class LoweringAlgebraTests(unittest.TestCase):
    def test_finite_full_time_lengths_parity_and_other_algebras(self):
        rng=np.random.default_rng(193)
        for length in [2,4,14,1428,12288]:
            z=rng.normal(size=(1,3,length+12)).astype(np.float32);w=rng.normal(size=(3,7)).astype(np.float32);b=rng.normal(size=3).astype(np.float32)
            expected=conv(z,w,b,2)
            for rewrite in [parity_batch1,parity_batch2,zero_expanded,shifted_terms]:
                np.testing.assert_array_equal(expected,rewrite(z,w,b))
                self.assertEqual((1,3,length),rewrite(z,w,b).shape)

    def test_existing_external_pad_kept_before_split_and_bias_once(self):
        x=np.arange(2*4*16,dtype=np.float32).reshape(2,4,16);w=np.arange(28,dtype=np.float32).reshape(4,7)/8;b=np.array([1,3,7,11],dtype=np.float32)
        for mode in ['constant','reflect','edge']:
            for pads in [(12,0),(6,6)]:  # actual source is causal edge (12,0)
                z=np.pad(x,((0,0),(0,0),pads),mode=mode)
                for rewrite in [parity_batch1,parity_batch2]:np.testing.assert_array_equal(conv(z,w,b,2),rewrite(z,w,b))
        z=np.zeros((1,4,28),dtype=np.float32)
        np.testing.assert_array_equal(parity_batch1(z,w,b),np.broadcast_to(b[None,:,None],(1,4,16)))

    def test_splitting_before_existing_edge_pad_is_not_equivalent(self):
        x=np.arange(8,dtype=np.float32).reshape(1,1,8);w=np.ones((1,7),dtype=np.float32);b=np.zeros(1,dtype=np.float32)
        correct=parity_batch1(np.pad(x,((0,0),(0,0),(12,0)),mode='edge'),w,b)
        even=conv(np.pad(x[:,:,::2],((0,0),(0,0),(6,0)),mode='edge'),w,b,1)
        odd=conv(np.pad(x[:,:,1::2],((0,0),(0,0),(6,0)),mode='edge'),w,b,1)
        wrong=np.stack((even,odd),axis=-1).reshape(1,1,8)
        self.assertFalse(np.array_equal(correct,wrong))

    def test_edges_kernel_taps_and_groups_do_not_mix(self):
        for index in [0,1,6,7,12,13,26,27]:
            z=np.zeros((1,3,28),dtype=np.float32);z[0,1,index]=1
            w=np.arange(21,dtype=np.float32).reshape(3,7)+1;b=np.zeros(3,dtype=np.float32)
            for rewrite in [parity_batch1,parity_batch2]:
                y=rewrite(z,w,b);np.testing.assert_array_equal(conv(z,w,b,2),y)
                self.assertFalse(y[:,[0,2],:].any())

    def test_real_shape_index_identity_without_full_model_arrays(self):
        length=12288;outputs=np.arange(length)[:,None];taps=np.arange(7)[None,:]
        original=outputs+2*taps
        phases=(outputs%2)+2*(outputs//2+taps)
        np.testing.assert_array_equal(original,phases)
        self.assertEqual((1,512,12300),(1,512,length+12));self.assertEqual(6150,(length+12)//2);self.assertEqual(6144,length//2)
        self.assertEqual(12300-1,int(original.max()))

    def test_zero_expanded_kernel_has_extra_nonfinite_propagation_risk(self):
        z=np.ones((1,1,16),dtype=np.float32);z[0,0,1]=np.inf;w=np.ones((1,7),dtype=np.float32);b=np.zeros(1,dtype=np.float32)
        with np.errstate(invalid='ignore'):
            original=conv(z,w,b,2);expanded=zero_expanded(z,w,b)
            np.testing.assert_array_equal(original,parity_batch1(z,w,b))
            np.testing.assert_array_equal(original,parity_batch2(z,w,b))
        self.assertTrue(np.isfinite(original[0,0,0]));self.assertTrue(np.isnan(expanded[0,0,0]))


if __name__=='__main__':unittest.main()
