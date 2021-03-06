from __future__ import print_function
from unittest import TestCase
import qelos as q
# from qelos.seq import Decoder, DecoderCell, ContextDecoderCell, AttentionDecoderCell, Attention, ContextDecoder, AttentionDecoder
# from qelos.rnn import q.RecStack, GRUCell, GRULayer, RecurrentStack
# from qelos.basic import q.Forward, Softmax, Stack, Lambda
import torch, numpy as np
from torch import nn
from torch.autograd import Variable


class TestDecoder(TestCase):
    def test_simple_decoder_shape(self):
        batsize, seqlen, vocsize = 5, 4, 7
        embdim, encdim, outdim = 10, 16, 10
        # model def
        decoder_cell = q.DecoderCell(
            nn.Embedding(vocsize, embdim, padding_idx=0),
            q.GRUCell(embdim, encdim),
            q.Forward(encdim, vocsize),
            q.Softmax()
        )
        decoder = decoder_cell.to_decoder()
        # end model def
        data = np.random.randint(0, vocsize, (batsize, seqlen))
        data = Variable(torch.LongTensor(data))

        decoded = decoder(data).data.numpy()
        self.assertEqual(decoded.shape, (batsize, seqlen, vocsize))     # shape check
        self.assertTrue(np.allclose(np.sum(decoded, axis=-1), np.ones_like(np.sum(decoded, axis=-1))))  # prob check

    def test_context_decoder_shape(self):
        batsize, seqlen, vocsize = 5, 4, 7
        embdim, encdim, outdim, ctxdim = 10, 16, 10, 8
        # model def
        decoder_cell = q.ContextDecoderCell(
            nn.Embedding(vocsize, embdim, padding_idx=0),
            q.GRUCell(embdim + ctxdim, encdim),
            q.Forward(encdim, vocsize),
            q.Softmax()
        )
        decoder = decoder_cell.to_decoder()
        # end model def
        data = np.random.randint(0, vocsize, (batsize, seqlen))
        data = Variable(torch.LongTensor(data))
        ctx = Variable(torch.FloatTensor(np.random.random((batsize, ctxdim))))

        decoded = decoder(data, ctx).data.numpy()
        self.assertEqual(decoded.shape, (batsize, seqlen, vocsize))  # shape check
        self.assertTrue(np.allclose(np.sum(decoded, axis=-1), np.ones_like(np.sum(decoded, axis=-1))))  # prob check

    def test_fast_context_decoder_shape(self):
        batsize, seqlen, vocsize = 5, 4, 7
        embdim, encdim, outdim, ctxdim = 10, 16, 10, 8
        # model def
        decoder = q.ContextDecoder(
            nn.Embedding(vocsize, embdim, padding_idx=0),
            q.RecurrentStack(
                q.GRULayer(embdim + ctxdim, encdim),
                q.Forward(encdim, vocsize),
                q.Softmax()
            )
        )
        # end model def
        data = np.random.randint(0, vocsize, (batsize, seqlen))
        data = Variable(torch.LongTensor(data))
        ctx = Variable(torch.FloatTensor(np.random.random((batsize, ctxdim))))

        decoded = decoder(data, ctx).data.numpy()
        self.assertEqual(decoded.shape, (batsize, seqlen, vocsize))  # shape check
        self.assertTrue(np.allclose(np.sum(decoded, axis=-1), np.ones_like(np.sum(decoded, axis=-1))))  # prob check


class TestAttentionDecoderCell(TestCase):
    def test_shapes(self):
        batsize, seqlen, inpdim = 5, 7, 8
        vocsize, embdim, encdim = 20, 9, 10
        ctxtoinitff = q.Forward(inpdim, encdim)
        coreff = q.Forward(encdim, encdim)
        initstategen = q.Lambda(lambda *x, **kw: coreff(ctxtoinitff(x[1][:, -1, :])), register_modules=coreff)

        decoder_cell = q.AttentionDecoderCell(
            attention=q.Attention().forward_gen(inpdim, encdim+embdim, encdim),
            embedder=nn.Embedding(vocsize, embdim),
            core=q.RecStack(
                q.GRUCell(embdim + inpdim, encdim),
                q.GRUCell(encdim, encdim),
                coreff
            ),
            smo=q.Stack(
                q.Forward(encdim+inpdim, encdim),
                q.Forward(encdim, vocsize),
                q.Softmax()
            ),
            init_state_gen=initstategen,
            ctx_to_decinp=True,
            ctx_to_smo=True,
            state_to_smo=True,
            decinp_to_att=True
        )
        decoder = decoder_cell.to_decoder()

        ctx = np.random.random((batsize, seqlen, inpdim))
        ctx = Variable(torch.FloatTensor(ctx))
        ctxmask = np.ones((batsize, seqlen))
        ctxmask[:, -2:] = 0
        ctxmask[[0, 1], -3:] = 0
        ctxmask = Variable(torch.FloatTensor(ctxmask))
        inp = np.random.randint(0, vocsize, (batsize, seqlen))
        inp = Variable(torch.LongTensor(inp))

        decoded = decoder(inp, ctx, ctxmask)

        self.assertEqual((batsize, seqlen, vocsize), decoded.size())
        self.assertTrue(np.allclose(
            np.sum(decoded.data.numpy(), axis=-1),
            np.ones_like(np.sum(decoded.data.numpy(), axis=-1))))
        print(decoded.size())


class TestAttentionDecoder(TestCase):
    def test_shapes(self):
        batsize, seqlen, inpdim = 5, 7, 8
        vocsize, embdim, encdim = 20, 9, 10
        ctxtoinitff = q.Forward(inpdim, encdim)
        coreff = q.Forward(encdim, encdim)
        initstategen = q.Lambda(lambda *x, **kw: coreff(ctxtoinitff(x[1][:, -1, :])), register_modules=coreff)

        decoder = q.AttentionDecoder(
            attention=q.Attention().forward_gen(inpdim, encdim+embdim, encdim),
            embedder=nn.Embedding(vocsize, embdim),
            core=q.RecurrentStack(
                q.GRULayer(embdim, encdim),
                q.GRULayer(encdim, encdim),
                coreff
            ),
            smo=q.Stack(
                q.Forward(encdim+inpdim, encdim),
                q.Forward(encdim, vocsize),
                q.Softmax(),
                q.argmap.spec(0),
            ),
            ctx_to_smo=True,
            state_to_smo=True,
            decinp_to_att=True
        )

        ctx = np.random.random((batsize, seqlen, inpdim))
        ctx = Variable(torch.FloatTensor(ctx))
        ctxmask = np.ones((batsize, seqlen))
        ctxmask[:, -2:] = 0
        ctxmask[[0, 1], -3:] = 0
        ctxmask = Variable(torch.FloatTensor(ctxmask))
        inp = np.random.randint(0, vocsize, (batsize, seqlen))
        inp = Variable(torch.LongTensor(inp))

        decoded = decoder(inp, ctx, ctxmask)

        self.assertEqual((batsize, seqlen, vocsize), decoded.size())
        self.assertTrue(np.allclose(
            np.sum(decoded.data.numpy(), axis=-1),
            np.ones_like(np.sum(decoded.data.numpy(), axis=-1))))
        print(decoded.size())


