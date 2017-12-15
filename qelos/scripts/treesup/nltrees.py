# -*- coding: utf-8 -*-
from __future__ import print_function
import qelos as q
import torch
import numpy as np
import random
import re
import sys
from collections import OrderedDict


class Node(object):
    leaf_suffix = "NC"
    last_suffix = "LS"

    def __init__(self, name, label=None, children=tuple(), **kw):
        super(Node, self).__init__(**kw)
        self.name = name    # name must be unique in a tree
        self.label = label
        self.children = tuple(children)

    @classmethod
    def parse(cls, inp, mode="ann", _toprec=True):
        assert(mode in "par ann".split())
        if mode == "ann":
            tokens = inp
            if _toprec:
                tokens = tokens.replace("  ", " ").strip().split()

            head, remainder = tokens[0], tokens[1:]
            xsplits = head.split("*")
            isleaf, islast = cls.leaf_suffix in xsplits, cls.last_suffix in xsplits
            x = xsplits[0]
            headname, headlabel = x, None
            if len(x.split("/")) == 2:
                headname, headlabel = x.split("/")
            if isleaf:
                ret = Node(headname, label=headlabel), islast, isleaf, remainder
            else:
                subnodes = []
                while True:
                    childnode, islastchild, isleafchild, remainder = cls.parse(remainder, mode=mode, _toprec=False)
                    subnodes.append(childnode)
                    if islastchild:
                        break
                subnode = Node(headname, label=headlabel, children=tuple(subnodes))
                ret = subnode, islast, isleaf, remainder
            if _toprec:
                return ret[0]
            else:
                return ret

    @property
    def is_leaf(self):
        return len(self.children) == 0

    @property
    def num_children(self):
        return len(self.children)

    def __str__(self):  return self.pp()
    def __repr__(self): return self.pp()

    def symbol(self, with_label=True, with_annotation=True):
        ret = self.name
        if with_label:
            ret += "/"+self.label if self.label is not None else ""
        if with_annotation:
            if self.is_leaf:
                ret += "*"+self.leaf_suffix
        return ret

    def pptree(self, arbitrary=False, _rec_arg=False, _top_rec=True):
        return self.pp(mode="tree", arbitrary=arbitrary, _rec_arg=_rec_arg, _top_rec=_top_rec)

    def pp(self, mode="par", arbitrary=False, _rec_arg=False, _top_rec=True):
        assert(mode in "par ann tree".split())
        children = list(self.children)
        if arbitrary:
            random.shuffle(children)
        selfstr = self.name + ("/" + self.label if self.label is not None else "")
        if mode == "par":
            children = [child.pp(mode=mode, arbitrary=arbitrary) for child in children]
            ret = selfstr + ("" if len(children) == 0 else " ({})".format(", ".join(children)))
        elif mode == "ann":
            _is_last = _rec_arg
            children = [child.pp(mode=mode, arbitrary=arbitrary, _rec_arg=_is_last_child)
                        for child, _is_last_child
                        in zip(children, [False] * (len(children)-1) + [True])]
            ret = selfstr + ("*NC" if len(children) == 0 else "") + ("*LS" if _is_last else "")
            ret += "" if len(children) == 0 else " ".join(children)
        elif mode == "tree":
            direction = "root" if _top_rec else _rec_arg
            if self.num_children > 0:
                def print_children(_children, _direction):
                    _lines = []
                    _dirs = ["up"] + ["middle"] * (len(_children) - 1) if _direction == "up" \
                        else ["middle"] * (len(_children) - 1) + ["down"]
                    for elem, _dir in zip(_children, _dirs):
                        elemlines = elem.pp(mode="tree", arbitrary=arbitrary, _rec_arg=_dir, _top_rec=False)
                        _lines += elemlines
                    return _lines

                parent = selfstr
                up_children, down_children = children[:len(children)//2], children[len(children)//2:]
                up_lines = print_children(up_children, "up")
                down_lines = print_children(down_children, "down")
                uplineprefix = "│" if direction == "middle" or direction == "down" else "" if direction == "root" else " "
                lines = [uplineprefix + " " * len(parent) + up_line for up_line in up_lines]
                parentprefix = "" if direction == "root" else '┌' if direction == "up" else '└' if direction == "down" else '├' if direction == "middle" else " "
                lines.append(parentprefix + parent + '┤')
                downlineprefix = "│" if direction == "middle" or direction == "up" else "" if direction == "root" else " "
                lines += [downlineprefix + " " * len(parent) + down_line for down_line in down_lines]
            else:
                connector = '┌' if direction == "up" else '└' if direction == "down" else '├' if direction == "middle" else ""
                lines = [connector + selfstr]
            if not _top_rec:
                return lines
            ret = "\n".join(lines)
        return ret

    def __eq__(self, other):
        same = self.name == other.name
        same &= self.label == other.label
        otherchildren = other.children + tuple()
        for child in self.children:
            found = False
            i = 0
            while i < len(otherchildren):
                if child == otherchildren[i]:
                    found = True
                    break
                i += 1
            if found:
                otherchildren = otherchildren[:i] + otherchildren[i+1:]
            same &= found
        return same


# TODO: implement special UniqueNodeGroupTracker that returns both nvt's and anvt's to oracle
class UniqueNodeTracker(object):
    """ nodes must have unique names,
        computes both nvt's (to sample gold from)
        and anvt's (to sample next token from) """
    # the allowable nvts must lead to a valid tree (covering all available names)
    def __init__(self, root, labels=None, **kw):
        super(UniqueNodeTracker, self).__init__(**kw)
        # store
        self.root = root
        self._possible_labels = labels  # must be a set
        # settings
        self._enable_allowable = True
        self._projective = False        # TODO support projective-only too
        # state
        self.current_node = self.root
        self._nvt = None
        self._anvt = None
        self._available_names = self.get_available_names(self.root) # {}
        self._lost_children = {}    # nodes we still have to attach
                                    # but which could not be attached to their true parent anymore
        self._stack = []    # to keep track of non-terminated parent sibling lists
        # start
        self.start()

    def reset(self):
        self.current_node = self.root
        self._nvt = None
        self._anvt = None
        self._available_names = self.get_available_names(self.root)
        self._lost_children = {}
        self._stack = []
        self.start()

    def start(self):
        return self.compute_nvts()

    def get_available_names(self, node):
        acc = {}
        acc[node.name] = node
        for child in node.children:
            acc.update(self.get_available_names(child))
        return acc

    def compute_nvts(self):     # computes nvts and anvts from current path and available names and labels
        # TODO
        # ! ensure that some valid tree is reachable with any anvt
        # region nvt
        nvt = set()
        own_children = list(filter(lambda x: x.name in self._available_names,
                                   self.current_node.children))
        lost_children = list(self._lost_children.values())
        possible_children = own_children + lost_children
        if len(possible_children) > 0:
            islast = False
            if len(possible_children) == 1:    # then must be last
                islast = True
            for child in possible_children:
                token = child.name
                token += ("/" + child.label) if child.label is not None else ""
                token += ("*" + child.leaf_suffix) if child.is_leaf else ""
                token += ("*" + child.last_suffix) if islast else ""
                nvt.add(token)

        # endregion
        self._nvt = nvt
        # region anvt
        anvt = set()
        available_names = list(self._available_names.keys())
        number_non_term_parents = sum([1 if len(_a) > 0 else 0
                                       for _a in self._stack])
        number_tokens_left = len(available_names)
        if self._possible_labels is None:
            possible_symbols = available_names
        else:
            possible_symbols = sum([[_name + "/" + _label for _label in self._possible_labels]
                                    for _name in available_names])

        for possible_symbol in possible_symbols:
            if number_tokens_left - 1 >= number_non_term_parents + 1:   # losing at least two potential terminators (will need one child and one sibling)
                anvt.add(possible_symbol)
            if number_tokens_left - 1 >= number_non_term_parents:   # losing at least on potential terminator in any of the below scenarios
                anvt.add(possible_symbol + "*" + self.root.last_suffix)
                anvt.add(possible_symbol + "*" + self.root.leaf_suffix)
            if number_non_term_parents > 0 or number_tokens_left == 1:     # must be last one left or the rest can be sent up
                anvt.add(possible_symbol + "*" + self.root.leaf_suffix + "*" + self.root.last_suffix)
        #endregion
        self._anvt = anvt
        # check if every nvt is in anvt:
        assert(len(nvt - anvt) == 0)
        return nvt, anvt

    def nxt(self, inpx):
        if len(self._stack) == 0:
            return set(), set()
        else:
            assert(inpx in self._anvt)

            # region process the input symbol x
            x, x_isleaf, x_islast = inpx + "", False, False
            inpxsplits = inpx.split("*")
            if len(inpxsplits) > 1:
                x, x_isleaf, x_islast = inpxsplits[0], self.root.leaf_suffix in inpxsplits, self.root.last_suffix in inpxsplits
            x_name, x_label = x, None
            xsplits = x.split("/")  # get label
            if len(xsplits) > 1:
                x_name, x_label = xsplits[0], xsplits[1]
            # endregion
            assert(x_name in self._available_names)

            # region stack management
            stack = self._stack + []

            stack[-1].append(x_name)
            if x_islast:
                stack[-1] = []      # empty sibling list
            if x_isleaf:    # should go up until next non-finished list or done
                while len(stack) > 0 and len(stack[-1]) == 0:
                    del stack[-1]
            else:           # should go down
                stack.append([])    # empty sibling list for deeper level

            self._stack = stack
            # endregion

            # region managing stored lists
            del self._available_names[x_name]
            if x_name in self._lost_children:
                del self._lost_children[x_name]
            if x_islast:    # if x is last, get children of current node we still had to decode
                            # and put them in lost children
                own_children = list(filter(lambda x: x.name in self._available_names,
                                   self.current_node.children))
                for own_child in own_children:
                    self._lost_children[own_child.name] = own_child
            # endregion

            self.current_node = self._available_names[x_name]

            return self.compute_nvts()


class NodeTracker(object):
    with_label = True

    def __init__(self, root, **kw):
        super(NodeTracker, self).__init__(**kw)
        self.root = root
        self.possible_paths = []
        self._nvt = None
        self.start()

    def reset(self):
        self.possible_paths = []
        self._nvt = None
        self.start()

    def start(self):
        self.possible_paths.append([[self.root]])
        allnvts = {self.root.symbol(with_label=self.with_label) + "*" + self.root.last_suffix}
        self._nvt = allnvts
        return allnvts

    def nxt(self, x):
        if len(self.possible_paths) == 0:
            return None
        else:
            if x not in self._nvt:
                print("!!!replacing x because not in vnt")
                assert(self._nvt is not None and len(self._nvt) > 0)
                x = random.sample(self._nvt, 1)[0]
            allnewpossiblepaths = []
            xsplits = x.split("*")
            x_isleaf, x_islast = False, False
            if len(xsplits) > 1:
                x, x_isleaf, x_islast = xsplits[0], self.root.leaf_suffix in xsplits, self.root.last_suffix in xsplits
            j = 0
            # check every possible path
            while j < len(self.possible_paths):
                possible_path = self.possible_paths[j]
                new_possible_paths = []
                i = 0
                node_islast = len(possible_path[-1]) == 1
                # check every token in top of stack
                while i < len(possible_path[-1]):
                    node = possible_path[-1][i]
                    if x == node.symbol(with_label=self.with_label, with_annotation=False) \
                            and node_islast == x_islast and node.is_leaf == x_isleaf:
                        new_possible_path = possible_path + []
                        new_possible_path[-1] = new_possible_path[-1] + []
                        del new_possible_path[-1][i]

                        if len(new_possible_path[-1]) == 0:
                            del new_possible_path[-1]

                        if not node.is_leaf:
                            new_possible_path.append(list(node.children))

                        if len(new_possible_path) > 0:
                            new_possible_paths.append(new_possible_path)
                    i += 1
                allnewpossiblepaths += new_possible_paths
                if len(new_possible_paths) == 0:
                    del self.possible_paths[j]
                else:
                    j += 1
            self.possible_paths = allnewpossiblepaths
        allnvts = set()
        for possible_path in self.possible_paths:
            if len(possible_path[-1]) == 1:
                topnode = possible_path[-1][0]
                allnvts.add(topnode.symbol(with_label=self.with_label, with_annotation=True)
                            + "*" + self.root.last_suffix)
            else:
                for topnode in possible_path[-1]:
                    allnvts.add(topnode.symbol(with_label=self.with_label, with_annotation=True))
        self._nvt = allnvts
        return allnvts


class Sentence(object):
    leaf_suffix = "NC"
    last_suffix = "LS"
    none_symbol = "<NONE>"
    root_token = "<ROOT>"
    parent_token = "<PARENT>"

    def __init__(self, x, **kw):
        super(Sentence, self).__init__(**kw)
        self.x = x
        self.tokenizer = lambda x: x.split()

    @property
    def tokens(self):
        return self.tokenizer(self.x)

    @classmethod
    def parse(cls):
        raise NotImplemented("use subclass")

    def track(self):
        raise NotImplemented("use subclass")

    @classmethod
    def build_dict_from(cls, sentences):
        raise NotImplemented("use subclass")


class OrderSentence(Sentence):
    def track(self):
        return OrderTracker(self)

    @classmethod
    def parse(cls, *tokens):
        if isinstance(tokens[0], (list, tuple)) and len(tokens) == 1:
            tokens = tokens[0]
        ret, tree, remainder = cls._parse_order(tokens)

        return ret, tree, remainder

    @classmethod
    def _parse_order(cls, tokens):
        head, remainder = tokens[0], tokens[1:]
        xsplits = head.split("*")
        isleaf, islast = cls.leaf_suffix in xsplits, cls.last_suffix in xsplits
        x = xsplits[0]
        isleaf = isleaf or cls.parent_token == x
        if isleaf:
            return x, head, remainder
        else:
            children, lsubtrees, rsubtrees, seen_parent = [], [], [], False
            while True:
                child, childtree, remainder = cls._parse_order(remainder)
                childtreeroot = childtree[0] if isinstance(childtree, tuple) else childtree
                islastchild = cls.last_suffix in childtreeroot.split("*")
                children.append(child)
                seen_parent = seen_parent or childtreeroot.split("*")[0] == cls.parent_token
                if not seen_parent:
                    lsubtrees.append(childtree)
                else:
                    if childtreeroot.split("*")[0] != cls.parent_token:
                        rsubtrees.append(childtree)
                if islastchild:
                    break
            subtreestring = " ".join(children)
            subtreestring = subtreestring.replace(cls.parent_token, x)
            if len(lsubtrees) == 0:
                lsubtrees = [""]
            if len(rsubtrees) == 0:
                rsubtrees = [""]
            subtree = (head, lsubtrees, rsubtrees)
            return subtreestring, subtree, remainder

    @classmethod
    def build_dict_from(cls, sentences):
        alltokens = set()
        for sentence in sentences:
            assert(isinstance(sentence, OrderSentence))
            tokens = sentence.tokens
            alltokens.update(tokens)
        indic = OrderedDict([("<MASK>", 0), ("<START>", 1), ("<STOP>", 2),
                             (cls.root_token, 3), (cls.parent_token, 4), (cls.parent_token+"*"+cls.last_suffix, 5)])
        outdic = OrderedDict()
        outdic.update(indic)
        offset = len(indic)
        alltokens = sorted(list(alltokens))
        alltokens_for_indic = ["<RARE>"] + alltokens
        alltokens_for_outdic = ["<RARE>"] + alltokens
        numtokens = len(alltokens_for_indic)
        newidx = 0
        for token in alltokens_for_indic:
            indic[token] = newidx + offset
            newidx += 1
        numtokens = len(alltokens_for_indic)
        newidx = 0
        for token in alltokens_for_outdic:
            outdic[token] = newidx + offset
            for i, suffix in enumerate(["*"+cls.leaf_suffix, "*"+cls.last_suffix, "*"+cls.leaf_suffix+"*"+cls.last_suffix]):
                outdic[token + suffix] = newidx + offset + (i + 1) * numtokens
            newidx += 1
        return indic, outdic


class BinarySentence(Sentence):
    @classmethod
    def parse(cls, *tokens):
        if isinstance(tokens[0], (list, tuple)):
            tokens = tokens[0]
        ret, tree, remainder = cls._parse_binary(tokens)
        ret = ret.replace("<NONE>", "").replace("  ", " ").strip()
        return ret, tree, remainder

    @classmethod
    def _parse_binary(cls, tokens):
        if len(tokens) == 0:
            return ""
            raise q.SumTingWongException("zero length tokens")
        else:
            token, remainder = tokens[0], tokens[1:]
            xsplits = token.split("*")
            token_isleaf = token == cls.none_symbol
            if len(xsplits) > 1 and xsplits[1] == cls.leaf_suffix:
                token, token_isleaf = xsplits[0], True
            if token_isleaf:
                return token, token, remainder
            else:
                left, ltree, remainder = cls._parse_binary(remainder)
                right, rtree, remainder = cls._parse_binary(remainder)
                return " ".join([left, token, right]), (token, ltree, rtree), remainder

    def track(self):
        return BinaryTracker(self)


class OrderTracker(object):
    """
    Tracks the sentence tree decoding process and provides different paths
    for a single sentence.
    Made for top-down depth-first binary tree decoding of sentences (sequences).
    Keeps track of multiple possible positions in th tree when ambiguous.
    """

    def __init__(self, sentence, **kw):
        super(OrderTracker, self).__init__(**kw)
        self.sentence = sentence    # list of words, original due tokens
        self._root_tokens = self.sentence.tokens
        #
        self.possible_paths = []    # list of possible paths (only non-one if ambiguity)
                                    # every possible path is a stack of shatterings or lists of due tokens
                                    # a shattering is a 3/2/1-tuple of lists of words that need to be covered
        self._nvt = None
        self.start()

    def reset(self):
        self.possible_paths = []
        self._nvt = None
        self.start()

    def start(self):
        self.possible_paths.append([(self._root_tokens,)])
        allnvts = set([t+"*"+Sentence.last_suffix for t in self._root_tokens])
        # allnvts.add(self._root_tokens[0] + "*" + Sentence.leaf_suffix)
        self._nvt = allnvts
        return allnvts

    def is_terminated(self):
        return len(self._nvt) == 0

    def nxt(self, x):
        if len(self.possible_paths) == 0:
            return None
        else:
            if x not in self._nvt:
                print("replacing x because not in vnt")
                assert(self._nvt is not None and len(self._nvt) > 0)
                x = random.sample(self._nvt, 1)[0]
            allnewpossiblepaths = []
            xsplits = x.split("*")
            x_isleaf = False
            x_islast = False
            if len(xsplits) > 1:
                x, x_isleaf, x_islast = xsplits[0], Sentence.leaf_suffix in xsplits, Sentence.last_suffix in xsplits
            x_isleaf = x_isleaf or x == self.sentence.parent_token
            j = 0
            # check every possible path
            while j < len(self.possible_paths):
                possible_path = self.possible_paths[j]  # stack of lists of due tokens
                new_possible_paths = []     # new possible paths from previous possible paths
                i = 0
                #
                possible_path_top = possible_path[-1]   # list of due tokens
                possible_path_top_next = possible_path_top[0]
                # check every token in top of stack
                while i < len(possible_path_top_next):
                    node = possible_path_top_next[i]
                    if node == x:
                        new_possible_path = possible_path + []
                        if x_isleaf:
                            new_possible_path[-1] = (possible_path_top_next[1:],) + possible_path_top[1:]
                        else:
                            # shatter the list
                            left, right = possible_path_top_next[:i], possible_path_top_next[i+1:]
                            new_possible_path.append((left, [Sentence.parent_token], right))

                        if len(new_possible_path[-1][0]) == 0:
                            new_possible_path[-1] = new_possible_path[-1][1:]

                        if x_islast:
                            if x_isleaf:
                                assert(len(new_possible_path[-1]) < 2)
                                remainder = new_possible_path[-1][0] if len(new_possible_path[-1]) > 0 else None
                                new_possible_path[-1] = tuple() + new_possible_path[-1][1:]
                                while len(new_possible_path) > 0 and len(new_possible_path[-1]) == 0:
                                    del new_possible_path[-1]
                                if len(new_possible_path) > 0:
                                    new_possible_path[-1] = ((remainder,) if remainder is not None else tuple())\
                                                            + new_possible_path[-1][1:]
                                    if len(new_possible_path[-1][0]) == 0:
                                        new_possible_path[-1] = new_possible_path[-1][1:]
                                else:
                                    assert(remainder is None or remainder == [])
                            else:
                                new_possible_path[-2] = new_possible_path[-2][1:]

                        if len(new_possible_path) > 0:
                            new_possible_paths.append(new_possible_path)
                    if x_isleaf:
                        break
                    i += 1
                allnewpossiblepaths += new_possible_paths
                if len(new_possible_paths) == 0:
                    del self.possible_paths[j]
                else:
                    j += 1
            self.possible_paths = allnewpossiblepaths

        # get nvts
        allnvts = set()
        for possible_path in self.possible_paths:
            if len(possible_path) == 0:     # done
                continue
            possible_path_top = possible_path[-1]
            possible_path_top_next = possible_path_top[0]
            if len(possible_path_top) == 3:     # in left decoding, can't have lasts
                if len(possible_path_top_next) == 1:    # can only be used as leaf
                    allnvts.add(possible_path_top_next[0] + "*" + self.sentence.leaf_suffix)
                else:   # first one can be leaf, others must be non-leaf (and non-last)
                    allnvts.update(set(possible_path_top_next))
                    allnvts.add(possible_path_top_next[0] + "*" + self.sentence.leaf_suffix)
            elif len(possible_path_top) == 2:   # parent token is next up
                number_non_term_parents = sum([1 if len(_a) > 0 else 0 for _a in possible_path[:-1]])
                number_tokens_left = len(possible_path_top[1])
                if number_non_term_parents < number_tokens_left:
                    allnvts.add(possible_path_top_next[0])
                if number_non_term_parents > 0 or number_tokens_left == 0:
                    allnvts.add(possible_path_top_next[0] + "*" + self.sentence.last_suffix)
            elif len(possible_path_top) == 1:   # in right decoding, can have lasts if not in top
                number_non_term_parents = sum([1 if len(_a) > 0 else 0 for _a in possible_path[:-1]])
                number_tokens_left = len(possible_path_top_next)
                if len(possible_path_top_next) == 1:
                    allnvts.add(possible_path_top_next[0] + "*" + self.sentence.leaf_suffix + "*" + self.sentence.last_suffix)
                else:
                    # if number_non_term_parents < number_tokens_left - 1:
                    for i in range(len(possible_path_top_next)):
                        nvt = possible_path_top_next[i]     # i is the number of possible left children
                        number_potential_last_siblings = len(possible_path_top_next) - i - 1
                        # number of needed last siblings will be +1 if we don't do LS
                        if number_potential_last_siblings - (1 if i == 0 else 0) \
                                >= number_non_term_parents + 1:
                            allnvts.add(nvt)
                        if number_potential_last_siblings - (1 if i == 0 else 0)\
                                >= number_non_term_parents: # can_be_LS: will need children
                            allnvts.add(nvt+"*"+self.sentence.last_suffix)
                        if i == 0 and number_potential_last_siblings >= number_non_term_parents + 1:      # can_be_NC: only if first element
                            allnvts.add(nvt+"*"+self.sentence.leaf_suffix)
                        if i == 0 and (len(possible_path_top_next) == 1 or number_non_term_parents > 0):
                            # can_be_NCLS: only if only element or rest can be sent up
                            allnvts.add(nvt+"*"+self.sentence.leaf_suffix+"*"+self.sentence.last_suffix)

                    # else:       # force terminate
                    #     allnvts.add(possible_path_top_next[0] + "*" + self.sentence.last_suffix + "*" + self.sentence.leaf_suffix)
        self._nvt = allnvts
        return allnvts


class BinaryTracker(object):
    """
    Tracks the sentence tree decoding process and provides different paths
    for a single sentence.
    Made for top-down depth-first binary tree decoding of sentences (sequences).
    Keeps track of multiple possible positions in th tree when ambiguous.
    """

    def __init__(self, sentence, **kw):
        super(BinaryTracker, self).__init__(**kw)
        self.sentence = sentence    # list of words, original due tokens
        self._root_tokens = self.sentence.tokens
        #
        self.possible_paths = []    # list of possible paths (only non-one if ambiguity)
                                    # every possible path is a stack of due tokens (list)
                                    # every due token list is a list of words that need to be covered from that level
        self._nvt = None
        self.start()

    def reset(self):
        self.possible_paths = []
        self._nvt = None
        self.start()

    def start(self):
        self.possible_paths.append([self._root_tokens])
        allnvts = set(self._root_tokens)
        self._nvt = allnvts
        return allnvts

    def nxt(self, x):
        if len(self.possible_paths) == 0:
            return None
        else:
            if x not in self._nvt:
                assert(self._nvt is not None and len(self._nvt) > 0)
                x = random.sample(self._nvt, 1)[0]
            allnewpossiblepaths = []
            xsplits = x.split("*")
            x_isleaf = False
            if len(xsplits) > 1 and self.sentence.leaf_suffix in xsplits:
                x, x_isleaf = xsplits[0], True
            j = 0
            # check every possible path
            while j < len(self.possible_paths):
                possible_path = self.possible_paths[j]  # stack of lists of due tokens
                new_possible_paths = []     # new possible paths from previous possible paths
                i = 0
                #
                possible_path_top = possible_path[-1]   # list of due tokens
                if len(possible_path_top) == 0:     # expecting a <NONE>
                    assert(x == self.sentence.none_symbol)
                    new_possible_path = possible_path + []
                    del new_possible_path[-1]
                    if len(new_possible_path) > 0:
                        new_possible_paths.append(new_possible_path)
                else:
                    node_isleaf = len(possible_path_top) == 1
                    # check every token in top of stack
                    while i < len(possible_path_top):
                        node = possible_path_top[i]
                        if node == x and (x_isleaf == node_isleaf):
                            if x_isleaf:
                                new_possible_path = possible_path + []
                                del new_possible_path[-1]
                            else:
                                new_possible_path = possible_path + []
                                left, right = possible_path_top[:i], possible_path_top[i+1:]
                                del new_possible_path[-1]
                                new_possible_path.append(right)
                                new_possible_path.append(left)
                            if len(new_possible_path) > 0:
                                new_possible_paths.append(new_possible_path)
                        i += 1
                allnewpossiblepaths += new_possible_paths
                if len(new_possible_paths) == 0:
                    del self.possible_paths[j]
                else:
                    j += 1
            self.possible_paths = allnewpossiblepaths

        # get nvts
        allnvts = set()
        for possible_path in self.possible_paths:
            if len(possible_path[-1]) == 1:
                topnode = possible_path[-1][0]
                allnvts.add(topnode + "*" + self.sentence.leaf_suffix)
            elif len(possible_path[-1]) == 0:
                allnvts.add(self.sentence.none_symbol)
            else:
                for topnode in possible_path[-1]:
                    allnvts.add(topnode)
        self._nvt = allnvts
        return allnvts


class GroupTracker(object):
    def __init__(self, trackables):
        super(GroupTracker, self).__init__()
        self.x = trackables
        indic, outdic = trackables[0].build_dict_from(trackables)
        self.dic = outdic
        self.rdic = {v: k for k, v in self.dic.items()}
        self.trackers = []
        self.D = outdic
        self.D_in = indic
        for xe in self.x:
            tracker = xe.track()
            self.trackers.append(tracker)

    def get_valid_next(self, eid):
        tracker = self.trackers[eid]
        nvt = tracker._nvt
        if len(nvt) == 0:  # done
            nvt = {"<MASK>"}
        nvt = map(lambda x: self.dic[x], nvt)
        return nvt

    def update(self, eid, x):
        tracker = self.trackers[eid]
        nvt = tracker._nvt
        if len(nvt) == 0:  # done
            pass
        else:
            x = self.rdic[x]
            tracker.nxt(x)

    def is_terminated(self, eid):
        return self.trackers[eid].is_terminated()

    def pp(self, x):
        xs = [self.rdic[xe] for xe in x if xe != self.dic["<MASK>"]]
        xstring = " ".join(xs)
        return xstring

    def reset(self):
        for tracker in self.trackers:
            tracker.reset()


def run_binary(x=0):
    _, tree, _ = Sentence.parse_binary("jumped he*NC on <NONE> roof the*NC after <NONE> dark*NC".split())
    pptree_bin(tree)

    sentence = Sentence("he jumped on the roof after the cat jumped on it")
    tracker = BinaryTracker(sentence)
    nvts = tracker._nvt
    tokens = []
    while len(nvts) > 0:
        token = random.sample(nvts, 1)[0]
        print(token)
        tokens.append(token)
        tracker.nxt(token)
        nvts = tracker._nvt
        print(nvts)
    print(" ".join(tokens))

    sentence, tree, remainder = Sentence.parse_binary(tokens + ["bleh"])
    print(sentence)
    print(tree)

    pptree_bin(tree)


def run_order(x=0):
    # sentence = Sentence("le chat rouge jumped on the roof after dark")
    # tracker = OrderTracker(sentence)
    # # tokens = "chat*LS le*NC <PARENT> jumped*LS rouge*NC <PARENT> after the on*NC <PARENT> roof*NC*LS <PARENT>*LS dark*NC*LS"
    # tokens = "le*LS <PARENT> chat <PARENT> rouge <PARENT> jumped <PARENT> on*NC the*NC*LS roof*NC*LS after*NC*LS dark*NC*LS"
    # # tokens = "on*LS chat le*NC <PARENT> rouge*LS*NC jumped*NC <PARENT> roof the*NC <PARENT>*LS dark*LS after*NC <PARENT>*LS"
    # # tokens = "on*LS jumped le*NC rouge chat*NC <PARENT>*LS <PARENT>*LS <PARENT> after*LS the*NC roof*NC <PARENT> dark*NC*LS"
    # # tokens = "on*LS jumped le*NC chat*NC rouge*NC <PARENT>*LS <PARENT> the <PARENT>*LS dark*LS roof*NC after*NC <PARENT>*LS"
    # # tokens = "rouge*LS le <PARENT>*LS chat*NC <PARENT> on*LS jumped*NC <PARENT> the <PARENT> after*LS roof*NC <PARENT>*LS dark*NC*LS"
    # for token in tokens.split():
    #     print(token)
    #     nvt = tracker.nxt(token)
    #     print(nvt)
    #
    # sys.exit()
    uniquetrees = set()
    sentence = Sentence("le chat rouge jumped on the roof after dark")
    num_samples = 100000
    for i in range(num_samples):
        tracker = OrderTracker(sentence)
        nvts = tracker._nvt
        tokens = []
        while len(nvts) > 0:
            token = random.sample(nvts, 1)[0]
            # print(token)
            tokens.append(token)
            tracker.nxt(token)
            nvts = tracker._nvt
            # print(nvts)
        # print(" ".join(tokens))
        uniquetrees.add(" ".join(tokens))

    # sys.exit()

        s, tree, remainder = Sentence.parse_order(tokens)
        # print(s)
        # pptree_order(tree)
        if i % 1000 == 0:
            print(i)

        assert(s == sentence.x)

    print("{} unique trees for the sentence after {} samples".format(len(uniquetrees), num_samples))

    sys.exit()
    tokens = "jumped*LS chat le*NC <PARENT>*LS rouge*NC <PARENT> on <PARENT> roof*LS the*NC <PARENT>*LS after*LS <PARENT> dark*NC*LS"
    for token in tokens.split():
        print(token)
        nvt = tracker.nxt(token)
        print(nvt)


def pptree_order(tree):
    lines = _pptree_order(tree, "root")
    for line in lines:
        print(line)


def _pptree_order(tree, direction):
    if isinstance(tree, tuple):
        parent = tree[0]
        up_lines = _pptree_order(tree[1], "up")
        down_lines = _pptree_order(tree[2], "down")
        uplineprefix = "│" if direction == "middle" or direction == "down" else "" if direction == "root" else " "
        lines = [uplineprefix + " "*len(parent) + up_line for up_line in up_lines]
        parentprefix = "" if direction == "root" else '┌' if direction == "up" else '└' if direction == "down" else '├' if direction == "middle" else " "
        lines.append(parentprefix + parent + '┤')
        downlineprefix = "│" if direction == "middle" or direction == "up" else "" if direction == "root" else " "
        lines += [downlineprefix + " "*len(parent) + down_line for down_line in down_lines]
    elif isinstance(tree, list):
        lines = []
        _dirs = ["up"] + ["middle"] * (len(tree)-1) if direction == "up" else ["middle"] * (len(tree) - 1) + ["down"]
        for elem, _dir in zip(tree, _dirs):
            elemlines = _pptree_order(elem, _dir)
            lines += elemlines
    else:
        connector = '┌' if direction == "up" else '└' if direction == "down" else '├' if direction == "middle" else ""
        lines = [connector + tree]
    return lines


def pptree_bin(tree):
    lines, _ = _pptree_bin(tree)
    for line in lines:
        print(line)


def _pptree_bin(tree):
    if isinstance(tree, tuple):
        parent = tree[0]
        up_lines, up_root_pos = _pptree_bin(tree[1])
        down_lines, down_root_pos = _pptree_bin(tree[2])
        lines = []
        for i, line in enumerate(up_lines):
            _line = " "*(len(parent))
            _line += '┌' if i == up_root_pos else "│" if i > up_root_pos else " "
            _line += line
            lines.append(_line)
        parent_pos = len(lines)
        lines.append(parent + '┤')
        # '├'
        for i, line in enumerate(down_lines):
            _line = " "*(len(parent))
            _line += '└' if i == down_root_pos else "│" if i < down_root_pos else " "
            _line += line
            lines.append(_line)
        return lines, parent_pos

    else:
        tree = tree.replace(Sentence.none_symbol, "")
        return [tree], 0


def run(x=0):
    treestr = "A/d*LS B/d C/d*NC D/a*NC E/b*NC F*LS G/h*NC H*NC*LS I*NC*LS"
    tree = Node.parse(treestr, mode="ann")
    # print(tree.pp(arbitrary=True, mode="tree"))

    tracker = NodeTracker(tree)
    uniquetrees = set()

    num_samples = 1000
    for i in range(num_samples):
        tracker.reset()
        nvts = tracker._nvt
        tokens = []
        while len(nvts) > 0:
            token = random.sample(nvts, 1)[0]
            # print(token)
            tokens.append(token)
            tracker.nxt(token)
            nvts = tracker._nvt
            # print(nvts)
        # print(" ".join(tokens))
        uniquetrees.add(" ".join(tokens))

        # sys.exit()

        recons = Node.parse(" ".join(tokens), mode="ann")
        if i % 1000 == 0:
            print(i)
        # print(recons.pptree())
        # print(tree.pptree())
        assert(recons == tree)

    print("{} unique trees for the sentence after {} samples".format(len(uniquetrees), num_samples))


if __name__ == "__main__":
    q.argprun(run)