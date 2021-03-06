from __future__ import print_function
from unittest import TestCase
from qelos.basic import Softmax, LogSoftmax, SoftmaxLog, DotDistance, CosineDistance, ForwardDistance, BilinearDistance, TrilinearDistance, LNormDistance
import torch
from torch.autograd import Variable
import numpy as np


class TestSoftmax(TestCase):
    def test_softmax_normal(self):
        b = Softmax()
        d = Variable(torch.FloatTensor(np.random.random((5, 3))))
        pred = b(d).data.numpy()
        predsums = np.sum(pred, axis=1)
        self.assertTrue(np.allclose(predsums, np.ones_like(predsums)))
        self.assertEqual(d.size(), pred.shape)

    def test_softmax_3D(self):
        b = Softmax()
        d = Variable(torch.FloatTensor(np.random.random((5, 4, 3))))
        pred = b(d).data.numpy()
        predsums = np.sum(pred, axis=2)
        self.assertTrue(np.allclose(predsums, np.ones_like(predsums)))
        self.assertEqual(d.size(), pred.shape)

    def test_softmax_5D(self):
        b = Softmax()
        d = Variable(torch.FloatTensor(np.random.random((7, 6, 5, 4, 3))))
        pred = b(d).data.numpy()
        predsums = np.sum(pred, axis=-1)
        self.assertTrue(np.allclose(predsums, np.ones_like(predsums)))
        self.assertEqual(d.size(), pred.shape)

    def test_softmax_normal_masked(self):
        b = Softmax()
        d = Variable(torch.FloatTensor(np.random.random((5, 3))))
        m = np.ones_like(d.data.numpy())
        m[:, 2] = 0
        m = Variable(torch.FloatTensor(m))
        pred, _ = b(d, m)
        pred = pred.data.numpy()
        print(pred)
        self.assertTrue(np.allclose(np.zeros_like(pred[:, 2]), pred[:, 2]))
        self.assertEqual(d.size(), pred.shape)
        predsums = np.sum(pred, axis=-1)
        self.assertTrue(np.allclose(predsums, np.ones_like(predsums)))

    def test_softmax_3D_masked(self):
        b = Softmax()
        d = Variable(torch.FloatTensor(np.random.random((5, 4, 3))))
        m = np.ones_like(d.data.numpy())
        m[:, :, 2] = 0
        m = Variable(torch.FloatTensor(m))
        pred, mask = b(d, m)
        pred = pred.data.numpy()
        print(pred)
        self.assertTrue(np.allclose(np.zeros_like(pred[:, :, 2]), pred[:, :, 2]))
        self.assertEqual(d.size(), pred.shape)
        predsums = np.sum(pred, axis=-1)
        self.assertTrue(np.allclose(predsums, np.ones_like(predsums)))

    def test_softmax_3D_prop_seq_mask(self):
        b = Softmax()
        d = Variable(torch.FloatTensor(np.random.random((5, 4, 3))))
        m = np.ones((5, 4))
        m[:, 2:] = 0
        m = Variable(torch.FloatTensor(m))
        pred, mask = b(d, m)
        predmask = mask.data.numpy()
        pred = pred.data.numpy()
        self.assertTrue(np.allclose(predmask, m.data.numpy()))
        predsums = np.sum(pred, axis=-1)
        self.assertTrue(np.allclose(predsums, np.ones_like(predsums)))

    def test_softmax_normal_with_temperature(self):
        b = Softmax(temperature=1e-6)
        d = Variable(torch.FloatTensor(np.random.random((5, 3))))
        pred = b(d).data.numpy()
        print(pred)

    def test_masked_softmax_numerical_stability(self):
        d = Variable(torch.FloatTensor(np.asarray([[-1e9, 1e9, 1], [-1e6, 1e6, 1], [-1e3, 1e3, 1], [-1e2, 1e2, 1], [-1e1, 1e1, 1], [-1, 1e2, 1], [1, 1e2, 1], [0.5, 1e2, 1]])))
        m = Variable(torch.FloatTensor(np.asarray([[1,0,1],[1,0,1],[1,0,1],[1,0,1],[1,0,1],[1,0,1],[1,0,1],[1,0,1]])))
        d2 = d[:, [0, 2]]
        o, _ = Softmax()(d, m)
        pred = o.data.numpy()
        pred2 = Softmax()(d2).data.numpy()
        pred3 = Softmax()(d).data.numpy()
        print(pred)
        print(pred2)
        print(pred3)
        self.assertTrue(np.allclose(pred[:, 1], np.zeros_like(pred[:, 1])))
        self.assertTrue(np.allclose(pred[:, [0, 2]], pred2))


class TestLogsoftmax(TestCase):
    def test_logsoftmax_normal(self):
        b = LogSoftmax()
        d = Variable(torch.FloatTensor(np.random.random((5, 3))))
        pred = b(d).data.numpy()
        predsums = np.sum(np.exp(pred), axis=1)
        self.assertTrue(np.allclose(predsums, np.ones_like(predsums)))
        self.assertEqual(d.size(), pred.shape)

    def test_logsoftmax_masked(self):
        b = LogSoftmax()
        d = Variable(torch.FloatTensor(np.random.random((5, 3))))
        m = np.ones_like(d.data.numpy())
        m[:, 2] = 0
        m = Variable(torch.FloatTensor(m))
        pred, _ = b(d, m)
        pred = pred.data.numpy()
        print(pred)
        self.assertTrue(np.allclose(np.zeros_like(pred[:, 2]), np.exp(pred)[:, 2]))
        self.assertEqual(d.size(), pred.shape)
        predsums = np.sum(np.exp(pred), axis=-1)
        print(predsums)
        self.assertTrue(np.allclose(predsums, np.ones_like(predsums)))

    def test_logsoftmax_masked_same_as_softmax(self):
        lsm = LogSoftmax()
        d = Variable(torch.FloatTensor(np.random.random((5, 3))))
        m = np.ones_like(d.data.numpy())
        m[:, 2] = 0
        m = Variable(torch.FloatTensor(m))
        pred, _ = lsm(d, m)
        pred = pred.data.numpy()
        print(pred)
        self.assertTrue(np.allclose(np.zeros_like(pred[:, 2]), np.exp(pred)[:, 2]))
        self.assertEqual(d.size(), pred.shape)
        predsums = np.sum(np.exp(pred), axis=-1)
        print(predsums)
        self.assertTrue(np.allclose(predsums, np.ones_like(predsums)))
        predexp, _ = Softmax()(d, m)
        predexp = predexp.data.numpy()
        self.assertTrue(np.allclose(predexp, np.exp(pred)))

    def test_masked_logsoftmax_numerical_stability(self):
        d = Variable(torch.FloatTensor(np.asarray([[-1e9, 1e9, 1], [-1e6, 1e6, 1], [-1e3, 1e3, 1], [-1e2, 1e2, 1], [-1e1, 1e1, 1], [-1, 1e2, 1], [1, 1e2, 1], [0.5, 1e2, 1]])))
        m = Variable(torch.FloatTensor(np.asarray([[1,0,1],[1,0,1],[1,0,1],[1,0,1],[1,0,1],[1,0,1],[1,0,1],[1,0,1]])))
        d2 = d[:, [0, 2]]
        o, _ = LogSoftmax()(d, m)
        pred = o.data.numpy()
        pred2 = LogSoftmax()(d2).data.numpy().astype("float64")
        pred3 = Softmax()(d2).data.numpy().astype("float64")
        print(pred)
        print(pred2)
        print(np.log(pred3))
        onetotwo = np.isclose(pred[:, [0, 2]], pred2)
        onetothree = np.isclose(pred[:, [0, 2]], np.log(pred3))
        self.assertTrue(np.all(onetothree | onetotwo))
        self.assertTrue(np.allclose(pred[:, 1], np.log(np.zeros_like(pred[:, 1]))))


class TestDistance(TestCase):
    def dorun_shape_tst_3D2D(self):
        a = Variable(torch.FloatTensor(np.random.random((5,3,4))))
        b = Variable(torch.FloatTensor(np.random.random((5,4))))
        d = self.m(a, b).data.numpy()
        self.assertEqual(d.shape, (5, 3))

    def test_all_dist_shape_3D2D(self):
        self.m = DotDistance()
        self.dorun_shape_tst_3D2D()
        self.m = CosineDistance()
        self.dorun_shape_tst_3D2D()
        self.m = ForwardDistance(4, 4, 8)
        self.dorun_shape_tst_3D2D()
        self.m = BilinearDistance(4, 4)
        self.dorun_shape_tst_3D2D()
        self.m = TrilinearDistance(4, 4, 8)
        self.dorun_shape_tst_3D2D()

    def dorun_shape_tst_2D2D(self):
        a = Variable(torch.FloatTensor(np.random.random((5,4))))
        b = Variable(torch.FloatTensor(np.random.random((5,4))))
        d = self.m(a, b).data.numpy()
        self.assertEqual(d.shape, (5,))

    def test_all_dist_shape_2D2D(self):
        self.m = DotDistance()
        self.dorun_shape_tst_2D2D()
        self.m = CosineDistance()
        self.dorun_shape_tst_2D2D()
        self.m = ForwardDistance(4, 4, 8)
        self.dorun_shape_tst_2D2D()
        self.m = BilinearDistance(4, 4)
        self.dorun_shape_tst_2D2D()
        self.m = TrilinearDistance(4, 4, 8)
        self.dorun_shape_tst_2D2D()

    def dorun_shape_tst_3D3D(self):
        a = Variable(torch.FloatTensor(np.random.random((5,3,4))))
        b = Variable(torch.FloatTensor(np.random.random((5,4,4))))
        d = self.m(a, b).data.numpy()
        self.assertEqual(d.shape, (5,3,4))

    def test_all_dist_shape_3D3D(self):
        self.m = DotDistance()
        self.dorun_shape_tst_3D3D()
        self.m = CosineDistance()
        self.dorun_shape_tst_3D3D()
        self.m = ForwardDistance(4, 4, 8)
        self.dorun_shape_tst_3D3D()
        self.m = BilinearDistance(4, 4)
        self.dorun_shape_tst_3D3D()
        self.m = TrilinearDistance(4, 4, 8)
        self.dorun_shape_tst_3D3D()

    def test_dot_same_as_numpy_2D2D(self):
        a = Variable(torch.FloatTensor(np.random.random((100, 200))))
        b = Variable(torch.FloatTensor(np.random.random((100, 200))))
        d = DotDistance()(a, b).data.numpy()
        a = a.data.numpy()
        b = b.data.numpy()
        npd = np.zeros((100,))
        for i in range(a.shape[0]):
            ijdist = np.dot(a[i], b[i])
            npd[i] = ijdist
        self.assertTrue(np.allclose(d, npd))

    def test_dot_same_as_numpy_3D2D(self):
        a = Variable(torch.FloatTensor(np.random.random((100, 50, 200))))
        b = Variable(torch.FloatTensor(np.random.random((100, 200))))
        d = DotDistance()(a, b).data.numpy()
        a = a.data.numpy()
        b = b.data.numpy()
        npd = np.zeros((100, 50))
        for i in range(a.shape[0]):
            for j in range(a.shape[1]):
                ijdist = np.dot(a[i, j], b[i])
                npd[i, j] = ijdist
        self.assertTrue(np.allclose(d, npd))

    def test_dot_same_as_numpy_3D3D(self):
        a = Variable(torch.FloatTensor(np.random.random((100, 50, 200))))
        b = Variable(torch.FloatTensor(np.random.random((100, 40, 200))))
        d = DotDistance()(a, b).data.numpy()
        a = a.data.numpy()
        b = b.data.numpy()
        npd = np.zeros((100, 50, 40))
        for i in range(a.shape[0]):
            for j in range(a.shape[1]):
                for k in range(b.shape[1]):
                    ijkdist = np.dot(a[i, j], b[i, k])
                    npd[i, j, k] = ijkdist
        self.assertTrue(np.allclose(d, npd))

    def test_cos_same_as_numpy_2D2D(self):
        a = Variable(torch.FloatTensor(np.random.random((100, 200))))
        b = Variable(torch.FloatTensor(np.random.random((100, 200))))
        d = CosineDistance()(a, b).data.numpy()
        a = a.data.numpy()
        b = b.data.numpy()
        npd = np.zeros((100,))
        for i in range(a.shape[0]):
            ijdist = np.dot(a[i], b[i])
            npd[i] = ijdist / (np.linalg.norm(a[i], 2) * np.linalg.norm(b[i], 2))
        self.assertTrue(np.allclose(d, npd))

    def test_cos_same_as_numpy_3D2D(self):
        a = Variable(torch.FloatTensor(np.random.random((100, 50, 200))))
        b = Variable(torch.FloatTensor(np.random.random((100, 200))))
        d = CosineDistance()(a, b).data.numpy()
        a = a.data.numpy()
        b = b.data.numpy()
        npd = np.zeros((100, 50))
        for i in range(a.shape[0]):
            for j in range(a.shape[1]):
                ijdist = np.dot(a[i, j], b[i])
                npd[i, j] = ijdist / (np.linalg.norm(a[i, j], 2) * np.linalg.norm(b[i], 2))
        self.assertTrue(np.allclose(d, npd))

    def test_cos_same_as_numpy_3D3D(self):
        a = Variable(torch.FloatTensor(np.random.random((10, 50, 20))))
        b = Variable(torch.FloatTensor(np.random.random((10, 40, 20))))
        d = CosineDistance()(a, b).data.numpy()
        a = a.data.numpy()
        b = b.data.numpy()
        npd = np.zeros((10, 50, 40))
        for i in range(a.shape[0]):
            for j in range(a.shape[1]):
                for k in range(b.shape[1]):
                    ijkdist = np.dot(a[i, j], b[i, k])
                    npd[i, j, k] = ijkdist / (np.linalg.norm(a[i, j], 2) * np.linalg.norm(b[i, k], 2))
        self.assertTrue(np.allclose(d, npd))

    def test_fwd_same_as_numpy_2D2D(self):
        a = Variable(torch.FloatTensor(np.random.random((100, 200))))
        b = Variable(torch.FloatTensor(np.random.random((100, 200))))
        dist = ForwardDistance(200, 200, 100, activation=None, use_bias=False)
        d = dist(a, b).data.numpy()
        lw, rw, aggw = dist.lblock.weight.data.numpy(), dist.rblock.weight.data.numpy(), dist.agg.data.numpy()
        a = a.data.numpy()
        b = b.data.numpy()
        npd = np.zeros((100,))
        for i in range(a.shape[0]):
            x = np.dot(np.dot(lw, a[i]) + np.dot(rw, b[i]), aggw)
            npd[i] = x
        self.assertTrue(np.allclose(d, npd, atol=1e-6))

    def test_fwd_same_as_numpy_3D2D(self):
        a = Variable(torch.FloatTensor(np.random.random((100, 50, 200))))
        b = Variable(torch.FloatTensor(np.random.random((100, 200))))
        dist = ForwardDistance(200, 200, 100, activation=None, use_bias=False)
        d = dist(a, b).data.numpy()
        lw, rw, aggw = dist.lblock.weight.data.numpy(), dist.rblock.weight.data.numpy(), dist.agg.data.numpy()
        a = a.data.numpy()
        b = b.data.numpy()
        npd = np.zeros((100, 50))
        for i in range(a.shape[0]):
            for j in range(a.shape[1]):
                x = np.dot(np.dot(lw, a[i, j]) + np.dot(rw, b[i]), aggw)
                npd[i, j] = x
        print(np.argwhere(abs(d - npd) > 1e-8))
        print(d[np.argwhere(abs(d - npd) > 1e-8)])
        print(npd[np.argwhere(abs(d - npd) > 1e-8)])
        print(np.argwhere(abs(d - npd) > 1e-7))
        self.assertTrue(np.allclose(d, npd, atol=1e-6))

    def test_fwd_same_as_numpy_3D3D(self):
        a = Variable(torch.FloatTensor(np.random.random((10, 50, 20))))
        b = Variable(torch.FloatTensor(np.random.random((10, 40, 20))))
        dist = ForwardDistance(20, 20, 100, activation=None, use_bias=False)
        d = dist(a, b).data.numpy()
        lw, rw, aggw = dist.lblock.weight.data.numpy(), dist.rblock.weight.data.numpy(), dist.agg.data.numpy()
        a = a.data.numpy()
        b = b.data.numpy()
        npd = np.zeros((10, 50, 40))
        for i in range(a.shape[0]):
            for j in range(a.shape[1]):
                for k in range(b.shape[1]):
                    x = np.dot(np.dot(lw, a[i, j]) + np.dot(rw, b[i, k]), aggw)
                    npd[i, j, k] = x
        print(np.argwhere(abs(d - npd) > 1e-8))
        #print(d[np.argwhere(abs(d - npd) > 1e-8)])
        #print(npd[np.argwhere(abs(d - npd) > 1e-8)])
        print(np.argwhere(abs(d - npd) > 1e-7))
        print(np.argwhere(abs(d - npd) > 1e-6))
        print(np.argwhere(abs(d - npd) > 1e-5))
        print(d[1])
        print(npd[1])
        print((d-npd)[1])
        self.assertTrue(np.allclose(d, npd, atol=1e-6))

    def test_fwd_same_as_numpy_3D3D_memsave(self):
        a = Variable(torch.FloatTensor(np.random.random((10, 5, 20))))
        b = Variable(torch.FloatTensor(np.random.random((10, 4, 20))))
        dist = ForwardDistance(20, 20, 10, activation=None, use_bias=False)
        dist.memsave = True
        d = dist(a, b).data.numpy()
        lw, rw, aggw = dist.lblock.weight.data.numpy(), dist.rblock.weight.data.numpy(), dist.agg.data.numpy()
        a = a.data.numpy()
        b = b.data.numpy()
        npd = np.zeros((10, 5, 4))
        for i in range(a.shape[0]):
            for j in range(a.shape[1]):
                for k in range(b.shape[1]):
                    x = np.dot(np.dot(lw, a[i, j]) + np.dot(rw, b[i, k]), aggw)
                    npd[i, j, k] = x
        print(np.argwhere(abs(d - npd) > 1e-8))
        #print(d[np.argwhere(abs(d - npd) > 1e-8)])
        #print(npd[np.argwhere(abs(d - npd) > 1e-8)])
        print(np.argwhere(abs(d - npd) > 1e-7))
        print(np.argwhere(abs(d - npd) > 1e-6))
        print(np.argwhere(abs(d - npd) > 1e-5))
        print(d[1])
        print(npd[1])
        print((d-npd)[1])
        self.assertTrue(np.allclose(d, npd, atol=1e-6))

    def test_bilin_same_as_numpy_2D2D(self):
        a = Variable(torch.FloatTensor(np.random.random((100, 200))))
        b = Variable(torch.FloatTensor(np.random.random((100, 200))))
        dist = BilinearDistance(200, 200)
        d = dist(a, b).data.numpy()
        w = dist.block.weight.squeeze().data.numpy()
        a = a.data.numpy()
        b = b.data.numpy()
        npd = np.zeros((100,))
        for i in range(a.shape[0]):
            x = np.dot(np.dot(a[i].T, w), b[i])
            npd[i] = x
        self.assertTrue(np.allclose(d, npd, atol=1e-6))

    def test_bilin_same_as_numpy_3D2D(self):
        a = Variable(torch.FloatTensor(np.random.random((100, 50, 200))))
        b = Variable(torch.FloatTensor(np.random.random((100, 200))))
        dist = BilinearDistance(200, 200)
        d = dist(a, b).data.numpy()
        w = dist.block.weight.squeeze().data.numpy()
        a = a.data.numpy()
        b = b.data.numpy()
        npd = np.zeros((100,50))
        for i in range(a.shape[0]):
            for j in range(a.shape[1]):
                x = np.dot(np.dot(a[i, j].T, w), b[i])
                npd[i, j] = x
        self.assertTrue(np.allclose(d, npd, atol=1e-5))

    def test_bilin_same_as_numpy_3D3D(self):
        a = Variable(torch.FloatTensor(np.random.random((10, 5, 20))))
        b = Variable(torch.FloatTensor(np.random.random((10, 4, 20))))
        dist = BilinearDistance(20, 20)
        d = dist(a, b).data.numpy()
        w = dist.block.weight.squeeze().data.numpy()
        a = a.data.numpy()
        b = b.data.numpy()
        npd = np.zeros((10, 5, 4))
        for i in range(a.shape[0]):
            for j in range(a.shape[1]):
                for k in range(b.shape[1]):
                    x = np.dot(np.dot(a[i, j].T, w), b[i, k])
                    npd[i, j, k] = x
        self.assertTrue(np.allclose(d, npd, atol=1e-5))


    def test_trilin_same_as_numpy_3D3D(self):
        a = Variable(torch.FloatTensor(np.random.random((10, 50, 20))))
        b = Variable(torch.FloatTensor(np.random.random((10, 40, 20))))
        dist = TrilinearDistance(20, 20, 10, activation=None, use_bias=False)
        dist.memsave = False
        d = dist(a, b).data.numpy()
        w = dist.block.weight.squeeze().data.numpy()
        aggw = dist.agg.data.numpy()
        a = a.data.numpy()
        b = b.data.numpy()
        npd = np.zeros((10, 50, 40))
        for i in range(a.shape[0]):
            for j in range(a.shape[1]):
                for k in range(b.shape[1]):
                    x = np.dot(np.dot(np.dot(a[i, j].T, w), b[i, k]), aggw)
                    npd[i, j, k] = x
        self.assertTrue(np.allclose(d, npd, atol=1e-6))

    def test_lnorm_same_as_numpy_2D2D(self):
        a = Variable(torch.FloatTensor(np.random.random((20, 2))))
        b = Variable(torch.FloatTensor(np.random.random((20, 2))))
        dist = LNormDistance(L=2)
        d = dist(a, b).data.numpy()
        a = a.data.numpy()
        b = b.data.numpy()
        npd = np.zeros((20,))
        for i in range(a.shape[0]):
            x = np.linalg.norm(a[i] - b[i])
            npd[i] = x
        print(d)
        print(npd)
        self.assertTrue(np.allclose(d, npd))

    def test_lnorm_same_as_numpy_3D2D(self):
        a = Variable(torch.FloatTensor(np.random.random((20, 5, 2))))
        b = Variable(torch.FloatTensor(np.random.random((20, 2))))
        dist = LNormDistance(L=2)
        d = dist(a, b).data.numpy()
        a = a.data.numpy()
        b = b.data.numpy()
        npd = np.zeros((20, 5))
        for i in range(a.shape[0]):
            for j in range(a.shape[1]):
                x = np.linalg.norm(a[i, j] - b[i])
                npd[i, j] = x
        print(d)
        print(npd)
        self.assertTrue(np.allclose(d, npd))

    def test_lnorm_same_as_numpy_3D3D(self):
        a = Variable(torch.FloatTensor(np.random.random((20, 5, 2))))
        b = Variable(torch.FloatTensor(np.random.random((20, 3, 2))))
        dist = LNormDistance(L=2)
        d = dist(a, b).data.numpy()
        a = a.data.numpy()
        b = b.data.numpy()
        npd = np.zeros((20, 5, 3))
        for i in range(a.shape[0]):
            for j in range(a.shape[1]):
                for k in range(b.shape[1]):
                    x = np.linalg.norm(a[i, j] - b[i, k])
                    npd[i, j, k] = x
        print(d[0])
        print(npd[0])
        self.assertTrue(np.allclose(d, npd))

    def test_lnorm_linear_sum_assignment(self):
        from scipy import optimize as spopt
        import qelos as q
        tt = q.ticktock()
        dim = 8
        a = Variable(torch.FloatTensor(np.random.random((dim, 2))))
        b = Variable(torch.FloatTensor(np.random.random((dim, 2))))
        dist = LNormDistance(L=2)(a.unsqueeze(0), b.unsqueeze(0)).squeeze(0)
        npdist = dist.cpu().data.numpy()
        tt.tick()
        ass_x, ass_y = spopt.linear_sum_assignment(npdist)
        tt.tock("spopt hungarian")
        validEMD = npdist[ass_x, ass_y].sum()
        if True:
            import itertools
            bfemd = np.infty
            tt.tick()
            perms = itertools.permutations(range(dim))
            idx = range(dim)
            for perm in perms:
                bfemd = min(bfemd, npdist[idx, perm].sum())
            tt.tock("brute force assignment")
            self.assertEqual(bfemd, validEMD)
        # self.assertTrue(False)


from torch import nn
import qelos as q

class TestGrad(TestCase):
    def test_multigrad(self):
        class Module(nn.Module):
            def __init__(self):
                super(Module, self).__init__()
                self.one = nn.Linear(3,3)
                self.two = nn.Linear(3,3)

            def forward(self, x):
                return self.two(self.one(x))

        net = Module()
        inp1 = q.var(torch.randn(3)).v
        inp2 = q.var(torch.randn(3)).v


        lossa = net(inp1).sum()
        lossa.backward()
        agrads = []
        for p in net.parameters():
            print(p.grad)
            agrads.append(p.grad.data.numpy()+0)

        net.zero_grad()

        lossb = net(inp2).sum()
        lossb.backward()
        bgrads = []
        for p in net.parameters():
            print(p.grad)
            bgrads.append(p.grad.data.numpy()+0)

        net.zero_grad()

        loss = net(inp2).sum() + net(inp1).sum()
        loss.backward()
        grads = []
        for p in net.parameters():
            print(p.grad)
            grads.append(p.grad.data.numpy()+0)

        net.zero_grad()

        lossa = net(inp1).sum()
        lossa.backward()
        lossb = net(inp2).sum()
        lossb.backward()

        sgrads = []
        for p in net.parameters():
            print(p.grad)
            sgrads.append(p.grad.data.numpy() + 0)

        for a, b, t, s in zip(agrads, bgrads, grads, sgrads):
            self.assertTrue(np.allclose(a+b, t))
            self.assertTrue(np.allclose(t, s))



        print("qsdf")