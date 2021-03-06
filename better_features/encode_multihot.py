import numpy as np

rank_lookups = {'A':14, 'K':13, 'Q':12, 'J':11, 'T':10, '9':9, '8':8, '7':7, '6':6, '5': 5, '4':4, '3':3, '2':2}
suit_lookups = {'D':0, 'C':1, 'H':2, 'S':3}

def encode_multihot(cards):
    """
    Encodes a list of cards in a similar fashion to one-hot encoding.
    Args:
        cards: list of str (ex. ['CT', 'S7'])
    Returns:
        tuple (np.ndarray size 13, np.ndarray size 4) 
    """
    encoded_ranks = np.zeros(13)
    encoded_suits = np.zeros(4)
    for card in cards:
        suit = card[0]
        rank = card[1]
        encoded_ranks[rank_lookups[rank]-2] += 1
        encoded_suits[suit_lookups[suit]] += 1
    return encoded_ranks, encoded_suits