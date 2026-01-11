import socket
import struct
from constants import *

class BlackjackClient:
    def __init__(self, num_rounds=None):
        self.team_name = "TeamPlayer"
        self.udp_port = UDP_PORT
        self.num_rounds = num_rounds if num_rounds is not None else 1
        
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

    def handle_gameplay(self, conn):
        """
        Handles the TCP communication during the game.
        """
        def _encode_decision(decision: str) -> bytes:
            return decision.encode('utf-8')[:5].ljust(5, b'\x00')

        def hand_value(cards):
            total = sum(cards)
            aces = cards.count(CARD_VALUE_ACE)
            while total > 21 and aces > 0:
                total -= 10
                aces -= 1
            return total

        round_index = 1
        rounds_left = self.num_rounds
        
        # 1. Initialize a buffer to hold incoming data across recv calls
        data_buffer = b""

        while rounds_left > 0:
            print(f"\n=== Round {round_index} ===")

            player_cards = []
            dealer_cards = []
            player_sum = None
            dealer_sum = None

            initial_packets = 0 
            waiting_for_player_card = False
            player_done = False
            
            # Flag to break out of the recv loop when round ends
            round_over = False

            while not round_over:
                # 2. Only receive if we don't have a full packet in the buffer
                if len(data_buffer) < 10:
                    try:
                        data = conn.recv(BUFFER_SIZE)
                        if not data:
                            print("Server closed connection during gameplay.")
                            return
                        data_buffer += data
                    except Exception as e:
                        print(f"Connection error: {e}")
                        return

                # 3. Process ALL complete packets currently in the buffer
                while len(data_buffer) >= 10:
                    # Slice off the first 10 bytes
                    packet = data_buffer[:10]
                    data_buffer = data_buffer[10:] # Keep the remaining bytes!

                    try:
                        cookie, msg_type, status, card_val, sum_val = struct.unpack('!IBBHH', packet)

                        if cookie != MAGIC_COOKIE or msg_type != MSG_TYPE_PAYLOAD:
                            continue

                        def describe_card(v: int) -> str:
                            if v == CARD_VALUE_ACE:
                                return "A(1/11)"
                            return str(v)

                        # Check result
                        if status in (RESULT_WIN, RESULT_LOSS, RESULT_TIE):
                            outcome = {
                                RESULT_WIN: "You win!",
                                RESULT_LOSS: "You lose.",
                                RESULT_TIE: "Tie.",
                            }.get(status, f"Finished with status {status}")
                            print(f"Result for round {round_index}: {outcome}")
                            
                            rounds_left -= 1
                            round_index += 1
                            round_over = True # Signal to exit the outer loop
                            break # Break the processing loop

                        # Logic to determine whose card it is
                        role = None
                        if initial_packets < 2:
                            player_cards.append(card_val)
                            player_sum = hand_value(player_cards)
                            initial_packets += 1
                            role = "player"
                        elif initial_packets == 2:
                            dealer_cards.append(card_val)
                            dealer_sum = sum_val
                            initial_packets += 1
                            role = "dealer"
                        else:
                            if not player_done and waiting_for_player_card:
                                player_cards.append(card_val)
                                player_sum = hand_value(player_cards)
                                waiting_for_player_card = False
                                role = "player"
                            else:
                                dealer_cards.append(card_val)
                                dealer_sum = sum_val
                                role = "dealer"

                        if role == "player":
                            pretty_player = [describe_card(c) for c in player_cards]
                            print(f"Your cards={pretty_player}, last card={describe_card(card_val)}, sum={player_sum}")
                        elif role == "dealer":
                            pretty_dealer = [describe_card(c) for c in dealer_cards]
                            print(f"Dealer cards={pretty_dealer}, last card={describe_card(card_val)}, dealer_sum={dealer_sum}")

                        if role == "player" and player_sum is not None and player_sum > 21:
                            print("Busted (sum > 21). Waiting for server result...")
                            player_done = True
                            waiting_for_player_card = False
                            continue

                        # Input Prompt
                        if (
                            status == RESULT_CONTINUE
                            and initial_packets >= 3  
                            and not player_done
                            and player_sum is not None
                            and player_sum <= 21
                            and len(player_cards) >= 2
                        ):
                            decision = input("Hit or Stand? [h/s]: ").strip().lower()
                            if decision.startswith('h'):
                                payload = _encode_decision("Hit")
                                waiting_for_player_card = True
                            else:
                                payload = _encode_decision("Stand")
                                player_done = True
                                waiting_for_player_card = False

                            conn.sendall(payload)

                    except Exception as e:
                        print(f"Error handling gameplay payload: {e}")

        print("\nAll rounds completed.")

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