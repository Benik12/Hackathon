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
            tcp_sock.close()

    def handle_gameplay(self, conn):
        """
        Handles the TCP communication during the game.
        """
        # Logic for sending 'Hit' or 'Stand'
        # IMPORTANT: Protocol requires 5 bytes for decision: "Hittt" or "Stand" 
        pass

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