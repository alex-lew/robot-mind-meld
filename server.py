"""
A simple word game powered by word embeddings.
"""
import re
import random
import numpy as np
import h5py
import wordfreq
from nltk.stem.lancaster import LancasterStemmer
from nltk.stem import PorterStemmer
from sanic import Sanic
from sanic.response import json


def standardized(term):
    """
    Breaks into underscore-separated words and replaces numbers with '#' signs.
    """
    tokens = wordfreq.tokenize(term.replace('_', ' '), 'xx')
    print(term, tokens)
    if tokens[0] == 'to':
        tokens = tokens[1:]
    return replace_numbers('_'.join(tokens))


def replace_numbers(s):
    """
    Replace digits with # in any term where a sequence of two digits appears.
    This operation is applied to text that passes through word2vec, so we
    should match it.
    """
    DOUBLE_DIGIT_RE = re.compile(r'[0-9][0-9]')
    DIGIT_RE = re.compile(r'[0-9]')
    if DOUBLE_DIGIT_RE.search(s):
        return DIGIT_RE.sub('#', s)
    else:
        return s


# Load word embeddings. Run create_data_file.py to create the
# embeddings.h5 file.
with h5py.File("words/embeddings.h5", "r") as f:
    mat = f['mat']['vecs'][:]
    words = [word.decode('utf-8') for word in f['mat']['words'][:]]
index = {word: i for i, word in enumerate(words)}

# Word stemming
ls = LancasterStemmer()
ps = PorterStemmer()
stem = lambda x: ps.stem(ls.stem(x))


def notAllowed(past, candidate):
    return any(
        map(lambda x: stem(x) == stem(candidate) or x.startswith(candidate) or candidate.startswith(x),
            past))


def nextWord(prevWord1, prevWord2, past):
    i1, i2 = index[prevWord1], index[prevWord2]
    closest = np.argsort(np.dot(mat, mat[i1, :]) * np.dot(mat, mat[i2, :]))
    closest = [words[word] for word in closest][-200:]
    closest = list(filter(lambda x: not notAllowed(past, x) and wordfreq.zipf_frequency(x, 'en') > 0, closest))
    print(closest[-1])
    return closest[-1]


def similarityScore(w1, w2):
    score = np.dot(mat[index[w1], :], mat[index[w2], :])
    return score


app = Sanic(__name__)
app.static("/", "./frontend/dist/index.html")
app.static("/static", "./frontend/dist/static/")


@app.route("/first_word")
async def first_word(request):
    w = random.choice(list(index))
    while wordfreq.zipf_frequency(w, 'en') == 0:
        w = random.choice(list(index))
    return json({"word": w})


@app.route("/next_word", methods=['POST'])
async def next_word(request):
    """
    1. Do I know the word? If not, send back "unknownWord: true"
    2. Are the words the same? If so, send back "unknownWord: false, victory: true"
    3. Otherwise, send back unknownWord: false, victory: false, nextWord: word, simScore: simScore
    """
    w1 = standardized(request.json['word1'])
    w2 = standardized(request.json['word2'])
    past = map(lambda w: standardized(w), request.json['past'])
    past = list(past) + [w1, w2]
    if w1 not in words:
        return json({"unknownWord": True})
    if stem(w1) == stem(w2):
        return json({"unknownWord": False, "victory": True})
    else:
        return json({
            "unknownWord": False,
            "victory": False,
            "nextWord": nextWord(w1, w2, past),
            "simScore": float(similarityScore(w1, w2))
        })


app.run(host="0.0.0.0", port=8000)
