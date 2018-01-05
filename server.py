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
stemmers = [
    ls.stem, ps.stem, lambda x: ps.stem(ls.stem(x)),
    lambda x: ls.stem(ps.stem(x))
]

# Acceptable first words
with open('words/acceptable_first_words.txt') as f:
    first_words = set(map(str.strip, f.readlines()))

# Unacceptable words to say
with open('words/bad_words.txt') as f:
    bad_words = set(map(str.strip, f.readlines()))

def lexicallyRelated(word1, word2):
    """
    Determine whether two words might be lexically related to one another.
    """
    return any(map(lambda stem: stem(word1) == stem(word2), stemmers)
              ) or word1.startswith(word2) or word2.startswith(word1)

def canUse(candidate, past):
    """
    Check whether a candidate is OK to use.
    """
    candidateFrequency = wordfreq.zipf_frequency(candidate, "en", wordlist="large")
    candidateRootFrequency = max(
        candidateFrequency,
        wordfreq.zipf_frequency(ps.stem(candidate), "en", wordlist="large"))

    # Reject words that are too infrequent or too frequent (like "a" or "the")
    if candidateFrequency < 2.3 or candidateFrequency > 6:
        return False

    # Mostly, this rejects '#'-containing words
    if not candidate.isalpha():
        return False

    # Is it a bad word?
    if candidate in bad_words:
        return False

    # Now, we check if we've used a related word before.
    if any(map(lambda w: lexicallyRelated(candidate, w), past)):
        return False

    # If we have a relatively infrequent word that is too related to
    # our past three rounds of words, we should reject it.
    if sum(similarityScore(x, candidate) for x in past[-6:]) > 2 and candidateRootFrequency < 3.2:
        return False

    # otherwise, we're ok!
    return True

# Precompute frequencies of all words in list
frequencies = np.array(
    [wordfreq.zipf_frequency(x, 'en', wordlist="large") for x in words])

def nextWord(prevWord1, prevWord2, past):
    """
    the further apart the two words are to each other, the less
    "frequency" should matter; it should not drown out subtle connections
    to both words. TODO: Improve this and use the fact that zipf is
    logarithmic.
    """
    currentCloseness = similarityScore(prevWord1, prevWord2)
    if currentCloseness < .09:
        freq_modifier = 1000.0
    elif currentCloseness < .25:
        freq_modifier = 200.0
    else:
        freq_modifier = 80.0
    i1, i2 = index[prevWord1], index[prevWord2]
    wordScores = (np.dot(mat, mat[i1, :]) * np.dot(mat, mat[i2, :])) + (frequencies / freq_modifier)
    bestWords = map(lambda i: words[i], reversed(np.argsort(wordScores)))
    bestWord = next(word for word in bestWords if canUse(word, past))
    print(prevWord1, prevWord2, bestWord)
    return bestWord

def similarityScore(w1, w2):
    score = np.dot(mat[index[w1], :], mat[index[w2], :])
    return score


app = Sanic(__name__)
app.static("/", "./frontend/dist/index.html")
app.static("/static", "./frontend/dist/static/")


@app.route("/first_word")
async def first_word(request):
    w = random.choice(list(index))
    while w not in first_words or wordfreq.zipf_frequency(w, 'en', wordlist="large") < 3.5:
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
    past = map(standardized, request.json['past'])
    past = list(past) + [w1, w2]
    if w1 not in words:
        return json({"unknownWord": True})
    if ps.stem(w1) == ps.stem(w2):
        return json({"unknownWord": False, "victory": True})
    else:
        return json({
            "unknownWord": False,
            "victory": False,
            "nextWord": nextWord(w1, w2, past),
            "simScore": float(similarityScore(w1, w2))
        })


app.run(host="0.0.0.0", port=8000)
