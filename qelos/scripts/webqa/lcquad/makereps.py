# -*- coding: utf8 -*-

from __future__ import print_function
import qelos as q
import torch
import re, dill as pickle, codecs, editdistance, numpy as np, os
from scipy.sparse import dok_matrix


def test_reps():
    (qpids, questionsm, querysm, vntmat), (_,_), (nl_emb, fl_emb, fl_linout) \
        = load_all()

    # region test nl emb
    print(nl_emb)
    rev_nl_emb_dic = {v: k for k, v in nl_emb.D.items()}
    x = q.var(questionsm.matrix).v
    xi = torch.cat([x[:5, 1], x[5:10, 9]], 0)
    y = nl_emb(xi)
    words = questionsm.pp(xi.data.numpy())
    print(xi)
    print(words)
    xi = xi.data.numpy()
    for i in range(10):
        wordid = xi[i]
        word = rev_nl_emb_dic[wordid]
        if word == "<MASK>":
            # print(y[0][i])
            # assert (np.allclose(y[0][i].data.numpy(), np.zeros_like(y[0][i].data.numpy())))
            assert(np.all(y[1][i].data.numpy() == 0))
        else:
            assert(np.all(y[1][i].data.numpy() == 1))
        if word in nl_emb.over.inner.D:
            # print(np.linalg.norm(y[0][i].data.numpy() - nl_emb.over.inner[word]))
            print("word {}({}) mapped to glove dict".format(word, wordid))
            assert(np.allclose(y[0][i].data.numpy(), nl_emb.over.inner[word]))
        else:
            print("word {}({}) mapped to special dict".format(word, wordid))
            assert(np.allclose(y[0][i].data.numpy(), nl_emb.base.over.inner[word]))
    # assert(np.allclose(y[0].data.numpy(), nl_emb.over.inner["comic"]))

    loss = y[0].sum()
    loss.backward()
    customwordsgrad = np.argwhere(nl_emb.base.over.inner.embedding.weight.grad.data.numpy()[:, 0])
    print(customwordsgrad)
    localrevdic = {v: k for k, v in nl_emb.base.over.inner.D.items()}
    nonzerocustomembtoken = localrevdic[customwordsgrad[0, 0]]
    print(nonzerocustomembtoken)
    assert(nonzerocustomembtoken == "<E0>")

    print("DONE: nl_emb correct")
    # endregion

    # region test typ emb
    print("type emb")
    typ_emb = fl_emb.over.inner
    print(typ_emb)
    print(typ_emb.D)
    testtypes = ["<http://dbpedia.org/ontology/MusicalArtist>",
                 "<http://dbpedia.org/ontology/Artist>",
                 "<http://dbpedia.org/ontology/Film>"]
    x = [typ_emb.D[e] for e in testtypes]
    typ_x = q.var(np.asarray(x, dtype="int64")).v
    typ_y, _ = typ_emb(typ_x)
    typ_data = typ_emb.data[typ_x]
    typ_words_revdic = {v: k for k, v in typ_emb.computer.layers[1].block.D.items()}
    # q.embed()
    accs = []
    for typ_data_row in typ_data:
        acc = ""
        for typ_data_row_tokenid in typ_data_row:
            acc += " " + typ_words_revdic[typ_data_row_tokenid.data[0]]
        print(acc)
        accs.append(acc)
    goldacces = [u" musical artist <MASK> <MASK> <MASK>",
                 u" artist <MASK> <MASK> <MASK> <MASK>",
                 u" film <MASK> <MASK> <MASK> <MASK>"]
    for goldacce, acce in zip(goldacces, accs):
        print(goldacce, acce)
        assert(acce == goldacce)

    print(x)

    loss = typ_y.sum()
    loss.backward()
    grulayer = typ_emb.computer.layers[3].nnlayer
    for param in grulayer.parameters():
        assert(param.grad is not None)
        assert(param.grad.norm().data[0] > 0)

    print("typ_emb: computer GRU grads non-zero")
    print("DONE: typ_emb correct")
    # endregion

    # region rel emb test
    print("rel emb")
    rel_emb = fl_emb.base.over.inner
    print(rel_emb)
    print(rel_emb.D)
    testrels = [":<http://dbpedia.org/ontology/spouse>",
                 ":<http://dbpedia.org/ontology/archipelago>",
                 ":<http://dbpedia.org/ontology/characterName>",
                 ":-<http://dbpedia.org/ontology/spouse>",
                 ":-<http://dbpedia.org/ontology/archipelago>",
                 ":-<http://dbpedia.org/ontology/characterName>"]
    x = [rel_emb.D[e] for e in testrels]
    rel_x = q.var(np.asarray(x, dtype="int64")).v
    rel_y, _ = rel_emb(rel_x)
    rel_data = rel_emb.data[rel_x]
    rel_words_revdic = {v: k for k, v in rel_emb.computer.layers[7].layers[1].block.D.items()}
    # q.embed()
    accs = []
    diracs = []
    for rel_data_row in rel_data:
        acc = ""
        diracs.append("fwd" if rel_data_row.data[0] == 0 else "rev")
        rel_data_row = rel_data_row[1:]
        for rel_data_row_tokenid in rel_data_row:
            acc += " " + rel_words_revdic[rel_data_row_tokenid.data[0]]
        print(acc)
        accs.append(acc)
    print(diracs)
    goldacces = [u" spouse <MASK> <MASK> <MASK>",
                 u" archipelago <MASK> <MASK> <MASK>",
                 u" character name <MASK> <MASK>",
                 u" spouse <MASK> <MASK> <MASK>",
                 u" archipelago <MASK> <MASK> <MASK>",
                 u" character name <MASK> <MASK>",
                 ]
    golddiracs = [u"fwd"] * 3 + [u"rev"] * 3
    for goldacce, golddirac, acce, dirac in zip(goldacces, golddiracs, accs, diracs):
        print(goldacce, acce)
        assert(dirac == golddirac)
        assert (acce == goldacce)

    loss = rel_y.sum()
    loss.backward()
    grulayer = rel_emb.computer.layers[7].layers[3].nnlayer
    for param in grulayer.parameters():
        print("param")
        assert (param.grad is not None)
        assert (param.grad.norm().data[0] > 0)

    print("rel_emb: computer gru param grads non-zero")

    dirembparam = rel_emb.computer.layers[4].embedding.weight
    assert(dirembparam.grad is not None and dirembparam.grad.norm().data[0] > 0)

    print("rel_emb: direction embedder grad non-zero")

    print(x)
    print("DONE: rel_emb correct")
    # endregion

    # region ent emb test
    print("ent embs")
    ent_emb = fl_emb.base.base.over.inner
    print(ent_emb)
    testents = [u"<http://dbpedia.org/resource/Piotr_Gliński>",
                u"<http://dbpedia.org/resource/Atlético_Petróleos_de_Luanda_(handball)>",
                u"<http://dbpedia.org/resource/Raša_(river)>"]

    x = [ent_emb.D[e] for e in testents]
    ent_x = q.var(np.asarray(x, dtype="int64")).v
    ent_y, _ = ent_emb(ent_x)
    ent_data = ent_emb.base.data[ent_x]
    ent_words_revdic = {v: k for k, v in ent_emb.base.computer.layers[1].block.D.items()}
    # q.embed()
    accs = []
    for ent_data_row in ent_data:
        acc = ""
        for ent_data_row_tokenid in ent_data_row:
            acc += " " + ent_words_revdic[ent_data_row_tokenid.data[0]]
        print(acc)
        accs.append(acc)
    goldacces = [u" piotr glinski" + u" <MASK>" * 8,
                 u" atletico petroleos de luanda" + u" <MASK>"*6,
                 u" rasa" + u" <MASK>"*9]
    for goldacce, acce in zip(goldacces, accs):
        print(goldacce, acce)
        assert (acce == goldacce)

    ent_typ_map_data = ent_emb.merg.data[ent_x]
    print(ent_typ_map_data)
    ent_typ_data = ent_emb.merg.computer.layers[1].data[ent_typ_map_data.squeeze()]
    ent_words_revdic = {v: k for k, v in ent_emb.merg.computer.layers[1].computer.layers[1].block.D.items()}
    # q.embed()
    accs = []
    for ent_data_row in ent_typ_data:
        acc = ""
        for ent_data_row_tokenid in ent_data_row:
            acc += " " + ent_words_revdic[ent_data_row_tokenid.data[0]]
        print(acc)
        accs.append(acc)
    goldacces = [u" scientist" + u" <MASK>" * 4,
                 u" soccer club" + u" <MASK>" * 3,
                 u" stream" + u" <MASK>" * 4]

    for goldacce, acce in zip(goldacces, accs):
        print(goldacce, acce)
        assert (acce == goldacce)

    loss = ent_y.sum()
    loss.backward()
    grulayer = ent_emb.base.computer.layers[3].nnlayer
    for param in grulayer.parameters():
        print("param")
        assert (param.grad is not None)
        assert (param.grad.norm().data[0] > 0)

    print("ent_emb: label computer gru param grads non-zero")

    grulayer = ent_emb.merg.computer.layers[1].computer.layers[3].nnlayer
    for param in grulayer.parameters():
        print("param")
        assert (param.grad is not None)
        assert (param.grad.norm().data[0] > 0)

    print("ent_emb: type label computer gru param grads non-zero")

    print("DONE: ent emb correct")
    # endregion

    # region special tokens
    print("special tokens test")
    special_emb = fl_emb.base.base.base.over.inner
    print(special_emb)
    print(special_emb.D)
    for k, v in special_emb.D.items():
        print(k, v, fl_emb.D[k])
    testspecial = ["<<TYPE>>",
                   "<<COUNT>>",
                   "<<BRANCH>>",
                   "<<JOIN>>",
                   "<<EQUALS>>",
                   "<RARE>",
                   "<START>",
                   "<END>",
                   "<MASK>",]
    x = [special_emb.D[e] for e in testspecial]
    special_x = q.var(np.asarray(x, dtype="int64")).v
    special_y, _ = special_emb(special_x)

    loss = special_y.sum()
    loss.backward()
    assert(special_emb.embedding.weight.grad.norm().data[0] > 0)
    print("special_emb: embedding grad non-zero")

    print("retrieved special token's vectors")
    # endregion

    # region test all fl_emb

    sepparams = set([param for param in typ_emb.parameters()]) \
                | set([param for param in rel_emb.parameters()]) \
                | set([param for param in ent_emb.parameters()]) \
                | set([param for param in special_emb.parameters()])
    sepparamgrads = {sepparam: sepparam.grad.data.numpy() + 0
                      for sepparam in sepparams
                      if sepparam.grad is not None}

    alltokens = testtypes + testrels + testents + testspecial
    expectedvecs = torch.cat([typ_y, rel_y, ent_y, special_y], 0)
    x = [fl_emb.D[token] for token in alltokens]
    all_x = q.var(np.asarray(x, dtype="int64")).v
    all_y, mask = fl_emb(all_x)

    expected_np = expectedvecs.data.numpy()
    returned_np = all_y.data.numpy()

    print(np.linalg.norm(expected_np - returned_np))
    assert(np.allclose(expected_np, returned_np))

    mask = mask.data.numpy()
    assert(mask[-1] == 0)
    assert(np.all(mask[:-1] == 1))

    fl_emb.zero_grad()

    loss = all_y.sum()
    loss.backward()
    print("all_emb: loss backwarded without throwing errors")

    allparams = set([param for param in fl_emb.parameters()])
    print("{} allparams, {} sepparams".format(len(allparams), len(sepparamgrads)))

    # q.embed()

    oogparams = {
        typ_emb.computer.layers[1].block.base.over.inner.embedding.weight,
        rel_emb.computer.layers[7].layers[1].block.base.over.inner.embedding.weight,
        ent_emb.base.computer.layers[1].block.base.over.inner.embedding.weight,
    }

    for allparam in allparams:
        if allparam.requires_grad:
            assert(allparam.grad is not None)
            if allparam.grad.data.norm() == 0:
                print(allparam.size())
                assert(allparam in oogparams)
            else:
                assert(allparam.grad.data.norm() > 0)
            if allparam in sepparamgrads:
                print("paramgrad")
                sepparamgrad = sepparamgrads[allparam]
                closeenough = np.allclose(allparam.grad.data.numpy(), sepparamgrad)
                if not closeenough:
                    print("norm diff: {}".format(np.linalg.norm(allparam.grad.data.numpy() - sepparamgrad)))
                assert(closeenough)

    print("fl_emb: gradients are equal to separated mode")

    print("fl_emb overriding correct")
    # endregion

    # region test all fl_linouts
    print("testing fl_linout")
    vntvocsize = vntmat[0, 0, 1]    # sparse batchable
    linvnt = np.zeros((5, vntvocsize), dtype="uint8")
    typids = np.asarray([fl_linout.D[abc] for abc in testtypes], dtype="int64")
    linvnt[0, typids] = 1
    relids = np.asarray([fl_linout.D[abc] for abc in testrels], dtype="int64")
    linvnt[1, relids] = 1
    entids = np.asarray([fl_linout.D[abc] for abc in testents], dtype="int64")
    linvnt[2, entids] = 1
    specids = np.asarray([fl_linout.D[abc] for abc in testspecial], dtype="int64")
    linvnt[3, specids] = 1
    allids = np.asarray([fl_linout.D[abc] for abc in alltokens], dtype="int64")
    linvnt[4, allids] = 1

    lindim = 50
    lin_inp = q.var(np.random.random((5, lindim)).astype("float32")).v
    lin_out = fl_linout(lin_inp, mask=q.var(linvnt).v)

    fl_linout.zero_grad()
    loss = lin_out.sum()
    loss.backward()

    oogparams = {
        fl_linout.over.inner.computer.layers[1].block.base.over.inner.embedding.weight,
        fl_linout.base.over.inner.computer.layers[7].layers[1].block.base.over.inner.embedding.weight,
        fl_linout.base.base.over.inner.base.computer.layers[1].block.base.over.inner.embedding.weight
    }

    for param in q.params_of(fl_linout):
        print("fl_linout paramgrad")
        assert(param.grad is not None)
        if param.grad.data.norm() == 0:
            assert(param in oogparams)
        if param.grad.data.norm() == 0:
            print(param.size())

    # q.embed()
    print("fl_linout worked without error (no assertions!!)")



    # endregion

    # q.embed()


def load_all(dim=50, glovedim=50, shared_computers=False, mergemode="sum",
             dirp="../../../../datasets/lcquad/",
             qfile="lcquad.multilin",
             lexfile="lcquad.multilin.lex",
             lexmatfile="lcquad.multilin.lexmats",
             vntfile="lcquad.multilin.vnt",
             replace_topic=True, replace_rdftype=True, replace_dbp=True):
    tt = q.ticktock("alloader")
    tt.tick("loading questions and reps")
    loadedq = load_questions(dirp+qfile, dirp+lexfile, replacetopic=replace_topic, replace_rdftype=replace_rdftype, replace_dbp=replace_dbp)
    nl_emb, fl_emb, fl_linout = get_reps(dim=dim, glovedim=glovedim, shared_computers=shared_computers, mergemode=mergemode,
                                         loaded_questions=loadedq, lexmatp=dirp+lexmatfile, replace_dbp=replace_dbp)

    tt.tock("loaded questions and reps").tick("loading vnts")
    vntmatcachep = "lcquad.multilin.vntmat.cache"
    if os.path.isfile(vntmatcachep):
        vntmat = q.load_sparse_tensor(open(vntmatcachep))
    else:
        vntmat = get_vnts(loadedq, fl_emb_d=fl_emb.D, replace_rdftype=replace_rdftype, replace_dbp=replace_dbp, vntp=dirp+vntfile)
        q.save_sparse_tensor(vntmat, open(vntmatcachep, "w"))
    tt.tock("loaded vnts")
    qpids, questionsm, querysm = loadedq

    txsplit = load_tx_split()
    trainids = []
    testids = []
    for i, qpid in enumerate(qpids):
        qid = qpid.split(".")[0]
        if txsplit[qid] == 0:
            trainids.append(i)
        elif txsplit[qid] == 1:
            testids.append(i)
    trainids = np.asarray(trainids, dtype="int64")
    testids = np.asarray(testids, dtype="int64")

    # q.embed()

    return (qpids, questionsm, querysm, vntmat), (trainids, testids), (nl_emb, fl_emb, fl_linout)


def get_vnts(loaded_questions=None,
        fl_emb_d=None,
        replace_rdftype=True, replace_dbp=True,
        vntp="../../../../datasets/lcquad/lcquad.multilin.vnt"):
    tt = q.ticktock("vnt loader")
    tt.tick("loading vnt file")
    vnt = pickle.load(open(vntp))
    tt.tock("loaded")

    qpids, questionsm, querysm = loaded_questions

    numex = querysm.matrix.shape[0]
    seqlen = querysm.matrix.shape[1]
    vocsize = max(fl_emb_d.values()) + 1
    print(numex, seqlen, vocsize)

    tt.tick("making vnts mat")
    # vntmat = [[dok_matrix((vocsize, 1), dtype="uint8") for i in range(seqlen)] for j in range(numex)]
    maxlen = 0
    for qpid in qpids:
        for timestep_vnt in vnt[qpid]:
            maxlen = max(maxlen, len(timestep_vnt))
    vntmat = np.zeros((numex, seqlen+1, maxlen+2), dtype="int64")
    vntmat[:, :, 2] = 1
    vntmat[:, :, 0] = 1
    vntmat[:, :, 1] = vocsize
    for i, qpid in enumerate(qpids):
        for j, timestep_vnt in enumerate(vnt[qpid]):
            l = 1
            if len(timestep_vnt) > 0:
                vntmat[i, j, 2] = 0
                l = 0
            for timestep_vnt_element in timestep_vnt:
                if replace_dbp:
                    timestep_vnt_element = re.sub("(:-?<http://dbpedia\.org/)property/([^>]+>)",
                                                  "\g<1>ontology/\g<2>", timestep_vnt_element)
                if replace_rdftype:
                    timestep_vnt_element = re.sub(":<http://www\.w3\.org/1999/02/22-rdf-syntax-ns#type>",
                                                  "<<TYPE>>", timestep_vnt_element)
                k = fl_emb_d[timestep_vnt_element]
                vntmat[i, j, l+2] = k+1
                l += 1
            vntmat[i, j, 0] = l     # number of elements
    tt.tock("made")
    # q.embed()
    return vntmat


def zerobasespecialglovecloneoverride(dim, dic, gloveemb):
    baseemb = q.ZeroWordEmb(dim=dim, worddic=dic)
    oogtokens = set(dic.keys()) - set(gloveemb.D.keys())
    oogtokens = ["<MASK>", "<RARE>"] + list(oogtokens)
    oogtokensdic = dict(zip(oogtokens, range(len(oogtokens))))
    oogtokenemb = q.WordEmb(dim=dim, worddic=oogtokensdic)
    emb = baseemb.override(oogtokenemb)
    gloveclonedic = set(dic.keys()) & set(gloveemb.D.keys()) - {"<MASK>", "<RARE>"}
    gloveclonedic = dict(zip(gloveclonedic, range(len(gloveclonedic))))
    gloveclone = gloveemb.subclone(gloveclonedic)
    emb = emb.override(gloveclone)
    return emb


def get_reps(dim=50, glovedim=50, shared_computers=False, mergemode="sum",
        loaded_questions=None, replace_dbp=True,
        lexmatp="../../../../datasets/lcquad/lcquad.multilin.lexmats"
        ):
    tt = q.ticktock("loader")
    qpids, questionsm, querysm = loaded_questions
    print(len(qpids), questionsm.matrix.shape, querysm.matrix.shape)

    tt.tick("loading lexinfo mats")
    lexinfo = pickle.load(open(lexmatp))
    tt.tock("loaded")

    gloveemb = q.PretrainedWordEmb(glovedim, incl_maskid=False, incl_rareid=False)

    tt.tick("building reps")
    # region get NL reps     # TODO: <RARE> should be trainable, <MASK> can also be from specials
    nl_emb = zerobasespecialglovecloneoverride(glovedim, questionsm.D, gloveemb)
    # endregion

    # region typ reps
    typsm = lexinfo["typsm"]
    typdic = lexinfo["typdic"]
    emb_typmat = zerobasespecialglovecloneoverride(glovedim, typsm.D, gloveemb)
    # baseemb_typmat = q.WordEmb(dim=glovedim, worddic=typsm.D)
    # emb_typmat = baseemb_typmat.override(gloveemb)
    typ_rep_inner = q.RecurrentStack(
        q.persist_kwargs(),
        emb_typmat,
        q.argmap.spec(0, mask=1),
        q.GRULayer(glovedim, dim).return_final("only")
    )
    typ_emb = q.ComputedWordEmb(data=typsm.matrix, computer=typ_rep_inner, worddic=typdic)
    if not shared_computers:
        typ_rep_inner = q.RecurrentStack(
            q.persist_kwargs(),
            emb_typmat,
            q.argmap.spec(0, mask=1),
            q.GRULayer(glovedim, dim).return_final("only")
        )
    typ_linout = q.ComputedWordLinout(data=typsm.matrix, computer=typ_rep_inner, worddic=typdic)
    # endregion

    # region rel reps
    relsm = lexinfo["relsm"]
    reldatamat = relsm.matrix
    reldatadic = relsm.D
    reldic = lexinfo["reldic"]

    if replace_dbp:
        newreldatamat = np.zeros_like(reldatamat)
        newreldic = {}
        i = 0
        for k, v in reldic.items():
            relname = k
            reldata = reldatamat[v]
            m = re.match("(:<http://dbpedia.org/)property/([^>]+>)", k)
            if m:
                relname = m.group(1) + "ontology/" + m.group(2)
            if relname not in newreldic:
                newreldic[relname] = i
                newreldatamat[i, :] = reldata
                i += 1
            else:
                # print(relname, k)
                pass
        reldatamat = newreldatamat[:i]
        reldic = newreldic

    # fwdorrev = np.ones((reldatamat.shape[0]), dtype="int32")
    reldic_rev = {k[0:1]+"-"+k[1:]: v + max(reldic.values()) + 1 for k, v in reldic.items()}
    reldic.update(reldic_rev)
    # fwdorrev = np.concatenate([fwdorrev * 0, fwdorrev * 1], axis=0)
    emb_relmat = zerobasespecialglovecloneoverride(glovedim, reldatadic, gloveemb)
    # baseemb_relmat = q.WordEmb(dim=glovedim, worddic=reldatadic)
    # emb_relmat = baseemb_relmat.override(gloveemb)

    rel_rep_inner_recu = q.RecurrentStack(
        q.persist_kwargs(),
        emb_relmat,
        q.argmap.spec(0, mask=1),
        q.GRULayer(glovedim, dim).return_final("only")
    )
    rel_direction_emb_emb = q.WordEmb(dim=dim, worddic={"FWD": 0, "REV": 1})
    rel_rep_inner = q.Stack(
        q.persist_kwargs(),
        q.Lambda(lambda x: (x[:, 0], x[:, 1:])),
        q.argsave.spec(direction=0, content=1),
        q.argmap.spec(["direction"]),
        rel_direction_emb_emb,
        q.argsave.spec(direction_emb=0),
        q.argmap.spec(["content"]),
        rel_rep_inner_recu,
        q.argmap.spec(0, ["direction_emb"]),
        q.Lambda(lambda x, y: x + y),
    )

    reldatamat = np.concatenate([np.zeros((reldatamat.shape[0], 1), dtype="int64"),
                                 reldatamat], axis=1)
    reldatamat_rev = reldatamat + 0
    reldatamat_rev[:, 0] = 1
    reldatamat = np.concatenate([reldatamat, reldatamat_rev], axis=0)

    rel_emb = q.ComputedWordEmb(data=reldatamat, computer=rel_rep_inner, worddic=reldic)

    # rel_emb(q.var(np.asarray([0, 1, 2, 3, 4, 616], dtype="int64")).v)

    if not shared_computers:
        rel_rep_inner_recu = q.RecurrentStack(
            q.persist_kwargs(),
            emb_relmat,
            q.argmap.spec(0, mask=1),
            q.GRULayer(glovedim, dim).return_final("only")
        )
        rel_direction_emb_emb = q.WordEmb(dim=dim, worddic={"FWD": 0, "REV": 1})
        rel_rep_inner = q.Stack(
            q.persist_kwargs(),
            q.Lambda(lambda x: (x[:, 0], x[:, 1:])),
            q.argsave.spec(direction=0, content=1),
            q.argmap.spec(["direction"]),
            rel_direction_emb_emb,
            q.argsave.spec(direction_emb=0),
            q.argmap.spec(["content"]),
            rel_rep_inner_recu,
            q.argmap.spec(0, ["direction_emb"]),
            q.Lambda(lambda x, y: x + y),
        )
    rel_linout = q.ComputedWordLinout(data=reldatamat, computer=rel_rep_inner, worddic=reldic)
    # endregion

    # region ent reps
    entsm = lexinfo["entsm"]
    entdic = lexinfo["entdic"]
    emb_entmat = zerobasespecialglovecloneoverride(glovedim, entsm.D, gloveemb)
    # baseemb_entmat = q.WordEmb(dim=glovedim, worddic=entsm.D)
    # emb_entmat = baseemb_entmat.override(gloveemb)
    ent_rep_inner = q.RecurrentStack(
        q.persist_kwargs(),
        emb_entmat,
        q.argmap.spec(0, mask=1),
        q.GRULayer(glovedim, dim).return_final("only")
    )
    ent_emb = q.ComputedWordEmb(data=entsm.matrix, computer=ent_rep_inner, worddic=entdic)
    if not shared_computers:
        ent_rep_inner = q.RecurrentStack(
            q.persist_kwargs(),
            emb_entmat,
            q.argmap.spec(0, mask=1),
            q.GRULayer(glovedim, dim).return_final("only")
        )
    ent_linout = q.ComputedWordLinout(data=entsm.matrix, computer=ent_rep_inner, worddic=entdic)
    # endregion

    # region ent typ reps
    typtrans = lexinfo["verybesttypes"][:, 0]
    if not shared_computers:
        typ_rep_inner_for_ent = q.RecurrentStack(
            q.persist_kwargs(),
            emb_typmat,
            q.argmap.spec(0, mask=1),
            q.GRULayer(glovedim, dim).return_final("only")
        )
        typ_emb_for_ent = q.ComputedWordEmb(data=typsm.matrix,
                computer=typ_rep_inner_for_ent, worddic=typdic)
    else:
        typ_emb_for_ent = typ_emb
    ent_typ_emb = q.ComputedWordEmb(
        data=typtrans,
        computer=q.Stack(
            q.persist_kwargs(), typ_emb_for_ent, q.argmap.spec(0)),
        worddic=entdic)

    if not shared_computers:
        typ_rep_inner_for_ent = q.RecurrentStack(
            q.persist_kwargs(),
            emb_typmat,
            q.argmap.spec(0, mask=1),
            q.GRULayer(glovedim, dim).return_final("only")
        )
        typ_emb_for_ent = q.ComputedWordEmb(data=typsm.matrix,
                computer=typ_rep_inner_for_ent, worddic=typdic)
    ent_typ_linout = q.ComputedWordLinout(
        data=typtrans,
        computer=q.Stack(
            q.persist_kwargs(),
            typ_emb_for_ent,
            q.argmap.spec(0)),
        worddic=entdic)

    ent_emb_final = ent_emb.merge(ent_typ_emb, mode=mergemode)
    ent_linout_final = ent_linout.merge(ent_typ_linout, mode=mergemode)
    # endregion

    # region merge reps
    basedict = {}
    basedict.update(querysm.D)
    nextvalididx = max(basedict.values()) + 1
    for k, v in reldic.items():
        if not k in basedict:
            basedict[k] = nextvalididx
            nextvalididx += 1
    for k, v in entdic.items():
        if not k in basedict:
            basedict[k] = nextvalididx
            nextvalididx += 1
    for k, v in typdic.items():
        if not k in basedict:
            basedict[k] = nextvalididx
            nextvalididx += 1

    for k, v in querysm.D.items():
        assert (basedict[k] == v)
    print("querysm.D and basedict consistent")

    specialdictkeys = set(basedict.keys()) - set(reldic.keys()) - set(entdic.keys()) - set(typdic.keys())
    specialdictsortedkeys = [k for k, v in sorted([(k, basedict[k]) for k in specialdictkeys], key=lambda x: x[1])]
    specialdict = dict(zip(specialdictsortedkeys, range(len(specialdictsortedkeys))))

    assert(specialdict["<MASK>"] == 0)

    special_emb = q.WordEmb(dim=dim, worddic=specialdict)
    special_linout = q.WordLinout(indim=dim, worddic=specialdict)

    fl_emb_base = q.ZeroWordEmb(dim=dim, worddic=basedict)
    fl_emb = fl_emb_base.override(special_emb).override(ent_emb_final)\
                        .override(rel_emb).override(typ_emb)

    fl_linout_base = q.ZeroWordLinout(indim=dim, worddic=basedict)
    fl_linout = fl_linout_base.override(special_linout).override(ent_linout_final)\
                              .override(rel_linout).override(typ_linout)

    for k, v in querysm.D.items():
        assert(fl_emb.D[k] == v)
        assert(fl_linout.D[k] == v)
    print("querysm and tgt's emb.D consistent")
    # endregion
    tt.tock("reps built")

    return nl_emb, fl_emb, fl_linout


def load_tx_split(p="../../../../datasets/lcquad/lcquad.tx.split"):
    tx = pickle.load(open(p))
    return tx


def load_questions(p="../../../../datasets/lcquad/lcquad.multilin",
                   lexp="../../../../datasets/lcquad/lcquad.multilin.lex",
                   replacetopic=True, replace_rdftype=True, replace_dbp=True):
    lexinfo = pickle.load(open(lexp))
    labels = lexinfo["labels"]
    # replaces property predicates with ontology !
    xsm = q.StringMatrix()
    ysm = q.StringMatrix()

    xsm.tokenize = lambda x: x.split()
    ysm.tokenize = lambda x: x.split()
    qpids = []

    qid = None
    qpid = None
    question = None
    parse = None
    with codecs.open(p, encoding="utf-8-sig") as f:
        for line in f:
            if len(line) > 0:
                qm = re.match("(?:[^Q]+)?(Q\d+):\s(.+)\n", line)
                if qm:
                    qid = qm.group(1)
                    question = qm.group(2)
                    continue
                pm = re.match("(Q\d+\.P\d+):\s(.+)\n", line)
                if pm:
                    qpid = pm.group(1)
                    parse = pm.group(2)
                    if qpid == "Q27.P1":
                        pass
                    if replace_dbp:
                        # replace property predicates by ontology
                        parse = re.sub("(:-?<http://dbpedia\.org/)property/([^>]+>)", "\g<1>ontology/\g<2>", parse)
                    if replace_rdftype:
                        parse = re.sub(":<http://www\.w3\.org/1999/02/22-rdf-syntax-ns#type>", "<<TYPE>>", parse)
                    topicent = parse.split()[0]
                    topiclabel = labels[topicent][0]
                    # find topic entity in question and replace
                    if replacetopic:
                        try:
                            newquestion, replaced = replace_longest_common_substring_span(topiclabel, "<E0>", question)
                            if len(topiclabel) * 1. / len(replaced) < 2:
                                # print(len(replaced) - len(topiclabel), qpid, newquestion, topiclabel, replaced)
                                # print("\t", parse)
                                xsm.add(newquestion)
                                qpids.append(qpid)
                                ysm.add(parse)
                        except Exception as e:
                            pass
                            # print("NO MATCH", question, qpid, topiclabel)
                            # raise e
                    else:
                        newquestion = question
                        xsm.add(newquestion)
                    continue
    xsm.finalize()
    ysm.finalize()
    return qpids, xsm, ysm


def replace_longest_common_substring_span_re(needle, repl, x):
    xtokens = q.tokenize(x)
    searchtokens = q.tokenize(needle)
    searchtokens = [re.escape(a) for a in searchtokens]
    searchretokens = ["(?:{})?".format(a) for a in searchtokens]
    searchre = "\s?".join(searchretokens)
    finditerator = re.finditer(searchre, " ".join(xtokens))

    longest_start, longest_end = None, None

    for found in finditerator:
        if found.start() < found.end() - 1:
            if longest_end is None or \
                found.end() - found.start() > longest_end - longest_start:
                longest_start, longest_end = found.start(), found.end()
            # print(found, found.start(), found.end())

    if longest_start is None:
        raise q.SumTingWongException("re couldn't find needle")
    joined = " ".join(xtokens)
    replaced = joined[longest_start:longest_end]
    out = joined[:longest_start] + " " + repl + " " + joined[longest_end:]
    out = re.sub("\s+", " ", out)
    return out, replaced


def replace_longest_common_substring_span(needle, repl, x):
    searchtokens = q.tokenize(needle)
    xtokens = q.tokenize(x)
    longest_start = None
    longest_end = None
    i = 0
    while i < len(xtokens):
        j = 1
        k = 0
        while j <= len(searchtokens):
            xtokenses = xtokens[i:i+j]
            searchtokenses = searchtokens[k:k+j]
            ed = edit_distance(" ".join(xtokenses), " ".join(searchtokenses))
            closeenough = ed < 2 or ed < (max(len(" ".join(xtokenses)), len(" ".join(searchtokenses))) / 5.)
            # closeenough = True
            # for l in range(j):
            #     if edit_distance(xtokenses[l], searchtokenses[l]) > 1:
            #         closeenough = False
            if closeenough:
                if longest_end is None or (longest_end - longest_start) < j:
                    longest_start, longest_end = i, i+j
            else:
                 break
            j += 1
        i += 1
    if longest_start is None:
        return replace_longest_common_substring_span_re(needle, repl, x)
    replaced = " ".join(xtokens[longest_start:longest_end])
    del xtokens[longest_start+1:longest_end]
    xtokens[longest_start] = repl
    out = " ".join(xtokens)
    return out, replaced


def edit_distance(a, b):
    if a == b:
        return 0
    else:
        return editdistance.eval(a, b)


if __name__ == "__main__":
    # print(replace_longest_common_substring_span_re("microsoft visual studio", "<E0>", "Name the company founded in US and created Visual Studio"))
    # get_vnts()
    test_reps()
    q.argprun(load_all)