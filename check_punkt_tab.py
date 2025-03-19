import nltk; try: nltk.data.find("tokenizers/punkt/punkt_tab"); print("punkt_tab exists!"); except LookupError as e: print(f"Error: {e}")
