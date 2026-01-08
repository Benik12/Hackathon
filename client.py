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
        # Enable port reuse to allow multiple clients on same machine [cite: 118]
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1) 
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
            # Protocol expects exactly 5 bytes; pad with NULs to be safe
            return decision.encode('utf-8')[:5].ljust(5, b'\x00')

        hand_sum = None
        hand_cards = []  # track visible cards for the client

        while True:
            data = conn.recv(BUFFER_SIZE)
            if not data:
                print("Server closed connection during gameplay.")
                break

            try:
                # Payload: Cookie(4), Type(1), Status(1), Card1(2), Card2(2)
                if len(data) < 10:
                    print("Received short payload; ignoring.")
                    continue

                cookie, msg_type, status, card1, card2 = struct.unpack('!IBBHH', data[:10])

                if cookie != MAGIC_COOKIE or msg_type != MSG_TYPE_PAYLOAD:
                    # Ignore unrelated/invalid packets
                    continue

                # Assume: card1 = new card value just dealt to client, card2 = updated player sum
                hand_cards.append(card1)
                hand_sum = card2
                print(f"Player cards={hand_cards}, last card={card1}, sum={hand_sum}, status={status}")

                # Auto-bust handling
                if status == RESULT_CONTINUE and hand_sum is not None and hand_sum > 21:
                    print("Busted (sum > 21). Waiting for server result...")
                    # No decision sent; server should soon send WIN/LOSS/TIE
                    continue

                if status == RESULT_CONTINUE:
                    decision = input("Hit or Stand? [h/s]: ").strip().lower()
                    if decision.startswith('h'):
                        payload = _encode_decision("Hit")
                    else:
                        payload = _encode_decision("Stand")

                    conn.sendall(payload)
                else:
                    # Round resolved: WIN/LOSS/TIE
                    outcome = {
                        RESULT_WIN: "You win!",
                        RESULT_LOSS: "You lose.",
                        RESULT_TIE: "Tie.",
                    }.get(status, f"Finished with status {status}")
                    print(outcome)
                    break

            except Exception as e:
                print(f"Error handling gameplay payload: {e}")

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