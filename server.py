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
        self.tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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
                print("Received incomplete request packet")
                return
            
            cookie, msg_type, rounds, team_name = struct.unpack('!IBB32s', data[:38])
            
            if cookie != MAGIC_COOKIE:
                print(f"Invalid magic cookie received: {hex(cookie)}")
                return
            
            if msg_type != MSG_TYPE_REQUEST:
                print(f"Invalid message type received: {hex(msg_type)}")
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

    def encode_card_for_network(self, card_value):
        """
        Convert internal card value to rank + suit encoding for network transmission.
        
        Args:
            card_value: Internal game value (2-11)
            
        Returns:
            tuple: (rank, suit) where rank is 1-13 and suit is 0-3
        """
        # Randomly assign a suit (0-3: Heart, Diamond, Club, Spade)
        suit = random.randint(0, 3)
        
        # Map internal value to rank
        if card_value == CARD_VALUE_ACE:  # 11
            rank = RANK_ACE  # Ace is rank 1
        elif card_value == 10:
            # Could be 10, J, Q, or K - randomly choose for variety
            rank = random.choice([10, RANK_JACK, RANK_QUEEN, RANK_KING])
        else:
            # 2-9 map directly to their rank
            rank = card_value
        
        return rank, suit

    def play_round(self, conn):
        def build_deck():
            # Standard 52-card deck, values only (Ace handled in hand_value)
            deck = []
            for _ in range(4):
                # 2-10, J, Q, K as 10, Ace as CARD_VALUE_ACE
                deck.extend([2,3,4,5,6,7,8,9,10,10,10,10,CARD_VALUE_ACE])
            random.shuffle(deck)
            return deck

        def hand_value(cards):
            total = sum(cards)
            aces = cards.count(CARD_VALUE_ACE)
            # Convert Aces from 11 to 1 as needed
            while total > 21 and aces > 0:
                total -= 10
                aces -= 1
            return total

        def draw_card(deck):
            if not deck:
                deck.extend(build_deck())
            return deck.pop()

        def send_payload(status, card_val):
            """
            Send payload packet to client.
            Format: Cookie(4) + Type(1) + Result(1) + card_rank(2) + card_suit(1) = 9 bytes
            
            Args:
                status: Game status (RESULT_WIN, RESULT_LOSS, RESULT_TIE, RESULT_CONTINUE)
                card_val: Internal card value (2-11), or 0 if no card to send
            """
            # Encode card to rank + suit if there's a card to send
            if card_val > 0:
                rank, suit = self.encode_card_for_network(card_val)
            else:
                rank, suit = 0, 0
            
            # Pack: Cookie(4) + Type(1) + Status(1) + Rank(2) + Suit(1) = 9 bytes
            packet = struct.pack('!IBBHB',
                                 MAGIC_COOKIE,
                                 MSG_TYPE_PAYLOAD,
                                 status,
                                 rank,
                                 suit)
            conn.sendall(packet)

        # Build deck and initial deal
        deck = build_deck()
        player_cards = [draw_card(deck), draw_card(deck)]
        dealer_cards = [draw_card(deck), draw_card(deck)]  # dealer_cards[1] is hidden initially

        player_sum = hand_value(player_cards)

        # Send player's initial two cards one by one
        send_payload(RESULT_CONTINUE, player_cards[0])
        send_payload(RESULT_CONTINUE, player_cards[1])

        # Send dealer's visible up-card (third initial packet)
        dealer_up_card = dealer_cards[0]
        send_payload(RESULT_CONTINUE, dealer_up_card)

        # Player turn
        while True:
            if player_sum > 21:
                send_payload(RESULT_LOSS, 0)
                return

            # Receive client decision: Cookie(4) + Type(1) + Decision(5) = 10 bytes
            decision_raw = conn.recv(10)
            if not decision_raw or len(decision_raw) < 10:
                print("Client disconnected or sent incomplete decision packet")
                return
            
            try:
                cookie, msg_type, decision_bytes = struct.unpack('!IB5s', decision_raw)
                
                # Validate magic cookie and message type
                if cookie != MAGIC_COOKIE:
                    print(f"Invalid magic cookie in decision: {hex(cookie)}")
                    return
                
                if msg_type != MSG_TYPE_PAYLOAD:
                    print(f"Invalid message type in decision: {hex(msg_type)}")
                    return
                
                decision = decision_bytes.decode('utf-8', errors='ignore').strip('\x00').lower()
                
            except Exception as e:
                print(f"Error parsing decision packet: {e}")
                return
            
            if decision.startswith('h'):
                # Hit - draw another card
                new_card = draw_card(deck)
                player_cards.append(new_card)
                player_sum = hand_value(player_cards)
                send_payload(RESULT_CONTINUE, new_card)
                continue
            else:
                # Stand - treat anything else as stand
                break

        # Dealer turn (only if player not busted)
        dealer_sum = hand_value(dealer_cards)

        # Reveal dealer's hidden card (second initial card) to the client
        send_payload(RESULT_CONTINUE, dealer_cards[1])

        while dealer_sum < 17:
            new_card = draw_card(deck)
            dealer_cards.append(new_card)
            dealer_sum = hand_value(dealer_cards)
            # Send dealer hits
            send_payload(RESULT_CONTINUE, new_card)

        # Decide outcome
        if dealer_sum > 21:
            result = RESULT_WIN
        elif player_sum > dealer_sum:
            result = RESULT_WIN
        elif dealer_sum > player_sum:
            result = RESULT_LOSS
        else:
            result = RESULT_TIE

        send_payload(result, 0)

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