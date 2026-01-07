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

# Card Suits
SUITS = ['Heart', 'Diamond', 'Club', 'Spade'] # [cite: 31, 103]