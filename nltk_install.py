#!/usr/bin/env python3

import sys
import os
import nltk

print("Python version:", sys.version)
print("NLTK version:", nltk.__version__)
print("NLTK data paths:", nltk.data.path)

print("\nInstalling punkt package to default location...")
nltk.download('punkt')
print("Installation to default location complete")

print("\nInstalling punkt package to app-specific location...")
nltk.download('punkt', download_dir='/app/nltk_data')
print("Installation to app location complete")

print("\nVerifying punkt_tab existence...")
try:
    punkt_tab_path = nltk.data.find('tokenizers/punkt/punkt_tab')
    print("Success! punkt_tab found at:", punkt_tab_path)
except LookupError as e:
    print("Error: punkt_tab not found -", str(e))
    
print("\nTesting tokenizer functionality...")
try:
    from nltk.tokenize import word_tokenize
    result = word_tokenize("Testing if the NLTK tokenizer works properly")
    print("Tokenization result:", result)
    print("Tokenizer is working correctly!")
except Exception as e:
    print("Error testing tokenizer:", str(e))

print("\nNLTK installation and verification complete.") 