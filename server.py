import socket
import struct
import threading
import time
import random
from constants import *

class BlackjackServer:
    def __init__(self, tcp_port=12345):
        self.tcp_port = tcp_port
        self.server_name = "TeamDealer"
        self.running = True
        # Setup TCP socket
        self.tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_sock.bind(('', self.tcp_port))
        self.tcp_sock.listen()

    def start(self):
        print(f"Server started, listening on IP address {self.get_local_ip()}") # [cite: 69]
        
        # Start UDP Broadcast thread
        udp_thread = threading.Thread(target=self.broadcast_offers, daemon=True)
        udp_thread.start()

        # Listen for TCP connections
        while self.running:
            try:
                client_sock, addr = self.tcp_sock.accept()
                print(f"New connection from {addr}")
                # Handle each client in a separate thread
                client_thread = threading.Thread(target=self.handle_client, args=(client_sock,))
                client_thread.start()
            except Exception as e:
                print(f"Error accepting connection: {e}")

    def broadcast_offers(self):
        """Sends UDP offers every 1 second."""
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        # Format: Cookie(4), Type(1), Port(2), Name(32) [cite: 85-90]
        # '!' = Network (Big Endian), I=Int(4), B=Byte(1), H=Short(2), 32s=String(32)
        packet = struct.pack('!IBH32s', 
                             MAGIC_COOKIE, 
                             MSG_TYPE_OFFER, 
                             self.tcp_port, 
                             self.server_name.encode('utf-8').ljust(32, b'\x00')) # Padding to 32 bytes

        while self.running:
            try:
                udp_sock.sendto(packet, ('<broadcast>', UDP_PORT))
                time.sleep(1) # [cite: 70]
            except Exception as e:
                print(f"Broadcasting error: {e}")

    def handle_client(self, conn):
        try:
            # 1. Receive Request Message (TCP)
            # Format: Cookie(4), Type(1), Rounds(1), Name(32) [cite: 91-95]
            data = conn.recv(1024)
            if len(data) < 38: # Minimum size check
                return
            
            cookie, msg_type, rounds, team_name = struct.unpack('!IBB32s', data[:38])
            
            if cookie != MAGIC_COOKIE or msg_type != MSG_TYPE_REQUEST:
                print("Invalid packet received.")
                return

            team_name = team_name.decode('utf-8').strip('\x00')
            print(f"Starting game with {team_name} for {rounds} rounds")

            # 2. Game Logic Loop
            for i in range(rounds):
                self.play_round(conn)
            
            print(f"Finished playing with {team_name}")
            
        except Exception as e:
            print(f"Client error: {e}")
        finally:
            conn.close()

    def play_round(self, conn):
        # Placeholder for game logic
        # Here you will implement: Deck creation, dealing cards, etc.
        # Sending cards uses the Payload format [cite: 96]
        pass

    def get_local_ip(self):
        # Utility to get local IP (simplified)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

if __name__ == "__main__":
    server = BlackjackServer()
    server.start()