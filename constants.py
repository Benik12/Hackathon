"""
Constants and protocol definitions for Blackijecky.
"""

# Networking Constants
UDP_PORT = 13122  # Listening port for UDP offers 
MAGIC_COOKIE = 0xabcddcba  # [cite: 87]
BUFFER_SIZE = 1024

# Message Types
MSG_TYPE_OFFER = 0x2    # [cite: 88]
MSG_TYPE_REQUEST = 0x3  # [cite: 93]
MSG_TYPE_PAYLOAD = 0x4  # [cite: 99]

# Game Results (Server -> Client)
RESULT_WIN = 0x3    # [cite: 101]
RESULT_LOSS = 0x2   # [cite: 101]
RESULT_TIE = 0x1    # [cite: 101]
RESULT_CONTINUE = 0x0 # Round is not over [cite: 101]

# Card encoding (values sent over the wire)
# 2-10  -> numeric cards
# 11    -> Ace (treated as 1 or 11 in scoring)
# Face cards (J, Q, K) are encoded as value 10
CARD_VALUE_ACE = 11

# Card Rank Constants (for network protocol)
RANK_ACE = 1
RANK_JACK = 11
RANK_QUEEN = 12
RANK_KING = 13

# Suit Constants (for network protocol)
SUIT_HEART = 0
SUIT_DIAMOND = 1
SUIT_CLUB = 2
SUIT_SPADE = 3

# Suits list
SUITS = ['Heart', 'Diamond', 'Club', 'Spade']  # [cite: 31, 103]
SUIT_SYMBOLS = ['♥', '♦', '♣', '♠']  # For display purposes