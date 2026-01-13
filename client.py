import socket
import struct
from constants import *

class BlackjackClient:
    def __init__(self, num_rounds=None):
        self.team_name = "TeamPlayer"  # TODO: Change to your creative team name!
        self.udp_port = UDP_PORT
        self.num_rounds = num_rounds if num_rounds is not None else 1
        self.wins = 0
        self.losses = 0
        self.ties = 0
        
    def start(self):
        print("Client started, listening for offer requests...") # [cite: 75]
        
        # UDP Listener setup
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Enable port reuse to allow multiple clients on same machine.
        # SO_REUSEPORT is not available on Windows, so fall back to SO_REUSEADDR.
        reuse_opt = getattr(socket, "SO_REUSEPORT", socket.SO_REUSEADDR)
        sock.setsockopt(socket.SOL_SOCKET, reuse_opt, 1)
        sock.bind(('', self.udp_port))

        try:
            while True:
                data, addr = sock.recvfrom(BUFFER_SIZE)
                try:
                    # Unpack Offer: Cookie(4), Type(1), Port(2), Name(32) [cite: 85-90]
                    cookie, msg_type, server_port, server_name = struct.unpack('!IBH32s', data)
                    
                    if cookie != MAGIC_COOKIE or msg_type != MSG_TYPE_OFFER:
                        continue
                    
                    server_ip = addr[0]
                    server_name = server_name.decode('utf-8').strip('\x00')
                    print(f"Received offer from {server_ip}, attempting to connect...") # [cite: 76]
                    
                    self.connect_to_server(server_ip, server_port)
                    break # After one session, logic resets 

                except Exception as e:
                    print(f"Error parsing UDP: {e}")
        finally:
            sock.close()
            print("UDP socket closed.")

    def connect_to_server(self, ip, port):
        tcp_sock = None
        try:
            tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_sock.connect((ip, port))
            
            # Send Request: Cookie(4), Type(1), Rounds(1), Name(32) [cite: 91-95]
            rounds = self.num_rounds
            packet = struct.pack('!IBB32s', 
                                 MAGIC_COOKIE, 
                                 MSG_TYPE_REQUEST, 
                                 rounds, 
                                 self.team_name.encode('utf-8').ljust(32, b'\x00'))
            tcp_sock.sendall(packet)
            
            # Start game loop 
            self.handle_gameplay(tcp_sock)
            
        except Exception as e:
            print(f"Connection failed: {e}")
        finally:
            if tcp_sock is not None:
                tcp_sock.close()

    def decode_card_from_network(self, rank, suit):
        """
        Convert rank + suit from network to game value and display string.
        
        Args:
            rank: Card rank (1-13)
            suit: Card suit (0-3)
            
        Returns:
            tuple: (card_value, display_string)
        """
        # Convert rank to game value
        if rank == RANK_ACE:  # Ace
            card_value = CARD_VALUE_ACE  # 11 (can be adjusted in hand_value)
            rank_str = "A"
        elif rank >= RANK_JACK:  # J, Q, K (11, 12, 13)
            card_value = 10
            rank_str = {RANK_JACK: "J", RANK_QUEEN: "Q", RANK_KING: "K"}.get(rank, str(rank))
        else:  # 2-10
            card_value = rank
            rank_str = str(rank)
        
        # Get suit symbol
        suit_symbol = SUIT_SYMBOLS[suit] if 0 <= suit <= 3 else "?"
        
        display_string = f"{rank_str}{suit_symbol}"
        return card_value, display_string

    def handle_gameplay(self, conn):
        """
        Handles the TCP communication during the game.
        """
        def _encode_decision(decision: str) -> bytes:
            """
            Encode player decision as proper payload packet.
            Format: Cookie(4) + Type(1) + Decision(5) = 10 bytes
            """
            decision_bytes = decision.encode('utf-8')[:5].ljust(5, b'\x00')
            packet = struct.pack('!IB5s', MAGIC_COOKIE, MSG_TYPE_PAYLOAD, decision_bytes)
            return packet

        def hand_value(cards):
            total = sum(cards)
            aces = cards.count(CARD_VALUE_ACE)
            while total > 21 and aces > 0:
                total -= 10
                aces -= 1
            return total

        round_index = 1
        rounds_left = self.num_rounds
        
        # Initialize a buffer to hold incoming data across recv calls
        data_buffer = b""

        while rounds_left > 0:
            print(f"\n=== Round {round_index} ===")

            player_cards = []
            player_card_displays = []  # For display purposes
            dealer_cards = []
            dealer_card_displays = []  # For display purposes
            player_sum = None
            dealer_sum = None

            initial_packets = 0 
            waiting_for_player_card = False
            player_done = False
            
            # Flag to break out of the recv loop when round ends
            round_over = False

            while not round_over:
                # Only receive if we don't have a full packet in the buffer
                # Server sends 9-byte packets now
                if len(data_buffer) < 9:
                    try:
                        data = conn.recv(BUFFER_SIZE)
                        if not data:
                            print("Server closed connection during gameplay.")
                            return
                        data_buffer += data
                    except Exception as e:
                        print(f"Connection error: {e}")
                        return

                # Process ALL complete packets currently in the buffer
                while len(data_buffer) >= 9:
                    # Slice off the first 9 bytes
                    packet = data_buffer[:9]
                    data_buffer = data_buffer[9:] # Keep the remaining bytes!

                    try:
                        # Unpack: Cookie(4) + Type(1) + Status(1) + Rank(2) + Suit(1) = 9 bytes
                        cookie, msg_type, status, card_rank, card_suit = struct.unpack('!IBBHB', packet)

                        if cookie != MAGIC_COOKIE:
                            print(f"Warning: Invalid magic cookie received: {hex(cookie)}")
                            continue
                        
                        if msg_type != MSG_TYPE_PAYLOAD:
                            print(f"Warning: Invalid message type received: {hex(msg_type)}")
                            continue

                        # Check result
                        if status in (RESULT_WIN, RESULT_LOSS, RESULT_TIE):
                            outcome = {
                                RESULT_WIN: "You win! 🎉",
                                RESULT_LOSS: "You lose.",
                                RESULT_TIE: "Tie.",
                            }.get(status, f"Finished with status {status}")
                            print(f"\nResult for round {round_index}: {outcome}")
                            
                            # Update statistics
                            if status == RESULT_WIN:
                                self.wins += 1
                            elif status == RESULT_LOSS:
                                self.losses += 1
                            elif status == RESULT_TIE:
                                self.ties += 1
                            
                            rounds_left -= 1
                            round_index += 1
                            round_over = True # Signal to exit the outer loop
                            break # Break the processing loop

                        # Decode card from rank + suit
                        card_value, card_display = self.decode_card_from_network(card_rank, card_suit)

                        # Logic to determine whose card it is
                        role = None
                        if initial_packets < 2:
                            # First 2 packets are player's initial cards
                            player_cards.append(card_value)
                            player_card_displays.append(card_display)
                            player_sum = hand_value(player_cards)
                            initial_packets += 1
                            role = "player"
                        elif initial_packets == 2:
                            # Third packet is dealer's visible card
                            dealer_cards.append(card_value)
                            dealer_card_displays.append(card_display)
                            dealer_sum = hand_value(dealer_cards)
                            initial_packets += 1
                            role = "dealer"
                        else:
                            # After initial deal, determine based on context
                            if not player_done and waiting_for_player_card:
                                player_cards.append(card_value)
                                player_card_displays.append(card_display)
                                player_sum = hand_value(player_cards)
                                waiting_for_player_card = False
                                role = "player"
                            else:
                                dealer_cards.append(card_value)
                                dealer_card_displays.append(card_display)
                                dealer_sum = hand_value(dealer_cards)
                                role = "dealer"

                        # Display the card
                        if role == "player":
                            cards_str = ', '.join(player_card_displays)
                            print(f"Your cards: [{cards_str}], last card: {card_display}, sum: {player_sum}")
                        elif role == "dealer":
                            cards_str = ', '.join(dealer_card_displays)
                            print(f"Dealer cards: [{cards_str}], last card: {card_display}, dealer sum: {dealer_sum}")

                        # Check for bust
                        if role == "player" and player_sum is not None and player_sum > 21:
                            print("💥 Busted (sum > 21)! Waiting for server result...")
                            player_done = True
                            waiting_for_player_card = False
                            continue

                        # Input Prompt - ask for decision after initial deal
                        if (
                            status == RESULT_CONTINUE
                            and initial_packets >= 3  # After initial 3 cards
                            and not player_done
                            and player_sum is not None
                            and player_sum <= 21
                            and len(player_cards) >= 2
                        ):
                            decision = input("Hit or Stand? [h/s]: ").strip().lower()
                            if decision.startswith('h'):
                                payload = _encode_decision("Hittt")
                                waiting_for_player_card = True
                            else:
                                payload = _encode_decision("Stand")
                                player_done = True
                                waiting_for_player_card = False

                            conn.sendall(payload)

                    except Exception as e:
                        print(f"Error handling gameplay payload: {e}")

        # Print final statistics
        print(f"\n{'='*50}")
        print(f"Finished playing {self.num_rounds} rounds!")
        print(f"Wins: {self.wins}, Losses: {self.losses}, Ties: {self.ties}")
        if self.num_rounds > 0:
            win_rate = (self.wins / self.num_rounds) * 100
            print(f"Win rate: {win_rate:.1f}%")
        print(f"{'='*50}")

if __name__ == "__main__":
    # Get number of rounds from user (default to 1 if invalid)
    try:
        rounds_input = input("Enter number of rounds (default 1): ").strip()
        num_rounds = int(rounds_input) if rounds_input else 1
        num_rounds = max(1, min(num_rounds, 255))  # Clamp between 1 and 255 (max for 1 byte)
    except ValueError:
        num_rounds = 1
    
    client = BlackjackClient(num_rounds=num_rounds)
    client.start()