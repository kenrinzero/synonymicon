"""Download NLTK data required by Synonymicon.

Run once after installing dependencies:
    python scripts/setup_nltk.py
"""
import nltk

for pkg in ('wordnet', 'omw-1.4'):
    nltk.download(pkg, quiet=False)
