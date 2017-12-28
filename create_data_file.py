#!/usr/bin/env python3
"""
create_data_file.py
Alex Lew
Downloads (if necessary) and processes Conceptnet Numberbatch
to normalize vectors and remove non-English words.
"""

import os
from urllib.request import urlretrieve
import h5py
import numpy as np

# Begin by downloading file if it doesn't exist
if not os.path.isfile('mini.h5'):
    print("Downloading Conceptnet Numberbatch word embeddings...")
    conceptnet_url = 'http://conceptnet.s3.amazonaws.com/precomputed-data/2016/numberbatch/17.06/mini.h5'
    urlretrieve(conceptnet_url, 'mini.h5')

with h5py.File('mini.h5', 'r') as original:
    all_embeddings = original['mat']['block0_values'][:]
    all_words = [word.decode('utf-8') for word in original['mat']['axis1'][:]]

word_index = {
    word[6:]: i
    for i, word in enumerate(all_words) if word.startswith('/c/en')
}
english_embedddings = all_embeddings[list(word_index.values())]
norms = np.linalg.norm(english_embedddings, axis=1)
normalized_embeddings = english_embedddings.astype('float32') / norms.astype(
    'float32').reshape([-1, 1])
encoded_word_array = np.array(
    [word.encode('utf-8') for word in word_index.keys()])

with h5py.File('embeddings.h5', 'w') as modified:
    grp = modified.create_group("mat")
    grp.create_dataset("vecs", data=normalized_embeddings)
    grp.create_dataset("words", data=encoded_word_array)
    modified.flush()
