from sanic import Sanic
from sanic.response import text, json
import numpy as np
import h5py
import re
import random
import wordfreq
from nltk.stem.lancaster import LancasterStemmer
from nltk.stem import PorterStemmer


# English-specific stopword handling
STOPWORDS = ['the', 'a', 'an']
DROP_FIRST = ['to']
DOUBLE_DIGIT_RE = re.compile(r'[0-9][0-9]')
DIGIT_RE = re.compile(r'[0-9]')


def standardized_uri(language, term):
    """
    Get a URI that is suitable to label a row of a vector space, by making sure
    that both ConceptNet's and word2vec's normalizations are applied to it.
    'language' should be a BCP 47 language code, such as 'en' for English.
    If the term already looks like a ConceptNet URI, it will only have its
    sequences of digits replaced by #. Otherwise, it will be turned into a
    ConceptNet URI in the given language, and then have its sequences of digits
    replaced.
    """
    if not (term.startswith('/') and term.count('/') >= 2):
        term = _standardized_concept_uri(language, term)
    return replace_numbers(term)


def english_filter(tokens):
    """
    Given a list of tokens, remove a small list of English stopwords. This
    helps to work with previous versions of ConceptNet, which often provided
    phrases such as 'an apple' and assumed they would be standardized to
    'apple'.
    """
    non_stopwords = [token for token in tokens if token not in STOPWORDS]
    while non_stopwords and non_stopwords[0] in DROP_FIRST:
        non_stopwords = non_stopwords[1:]
    if non_stopwords:
        return non_stopwords
    else:
        return tokens


def replace_numbers(s):
    """
    Replace digits with # in any term where a sequence of two digits appears.
    This operation is applied to text that passes through word2vec, so we
    should match it.
    """
    if DOUBLE_DIGIT_RE.search(s):
        return DIGIT_RE.sub('#', s)
    else:
        return s


def _standardized_concept_uri(language, term):
    if language == 'en':
        token_filter = english_filter
    else:
        token_filter = None
    language = language.lower()
    norm_text = _standardized_text(term, token_filter)
    return norm_text #'/c/{}/{}'.format(language, norm_text)


def _standardized_text(text, token_filter):
    tokens = simple_tokenize(text.replace('_', ' '))
    if token_filter is not None:
        tokens = token_filter(tokens)
    return '_'.join(tokens)


def simple_tokenize(text):
    """
    Tokenize text using the default wordfreq rules.
    """
    return wordfreq.tokenize(text, 'xx')

with h5py.File("mini.h5", "r") as f:
    mat = f['mat']['block0_values'][:]
    words = f['mat']['axis1'][:]

index = {word.decode('utf-8')[6:]: i for i, word in enumerate(words) if word.decode('utf-8').startswith('/c/en')}
mat = mat[list(index.values())]
words = list(index.keys())
index = {word: i for i, word in enumerate(words)}
norms = np.linalg.norm(mat, axis=1)
mat = mat.astype(float) / np.reshape(norms, [-1, 1])

ls = LancasterStemmer()
ps = PorterStemmer()
stem = lambda x: ps.stem(ls.stem(x))
def notAllowed(past, candidate):
    return any(map(lambda x: stem(x) == stem(candidate) or x.startswith(candidate) or candidate.startswith(x), past))

def nextWord(prevWord1, prevWord2, past):
    i1, i2 = index[prevWord1], index[prevWord2]
    closest = np.argsort(np.dot(mat, mat[i1, :]) * np.dot(mat, mat[i2, :]))
    closest = [words[word] for word in closest][-200:]
    closest = list(filter(lambda x: not notAllowed(past, x) and wordfreq.zipf_frequency(x, 'en') > 0, closest))
    return closest[-1]

def similarity(w1, w2):
    return np.dot(mat[index[w1], :], mat[index[w2], :])


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

    w1 = standardized_uri('en', request.json['word1'])
    w2 = standardized_uri('en', request.json['word2'])
    past = map(lambda w: standardized_uri('en',w), request.json['past'])
    past = list(past) + [w1, w2]
    if w1 not in words:
        return json({"unknownWord": True})
    if stem(w1) == stem(w2):
        return json({"unknownWord": False, "victory": True})
    else:
        return json({"unknownWord": False, "victory": False,
         "nextWord": nextWord(w1, w2, past), 
         "simScore": similarity(w1, w2)})

app.run(host="0.0.0.0", port=8000)
