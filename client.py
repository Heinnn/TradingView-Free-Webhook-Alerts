import socket

def send_message(message, server_address='localhost', server_port=65432):
    try:
        # Create a socket connection
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            print(f"Connecting to {server_address} on port {server_port}")
            client_socket.connect((server_address, server_port))  # Connect to the server

            print(f'Sending message: {message}')
            client_socket.sendall(message.encode())  # Send the message

            # Receive the response
            data = client_socket.recv(1024)  # Receive up to 1024 bytes
            print(f"Received response: {data.decode()}")

    except Exception as e:
        print(f"Failed to send message: {e}")
        
        
message = '''{
                    "action": "SHORT",
                    "ticker": "XAUUSD",
                    "price": "2609.795",
                    "tp": "",
                    "sl": "2620.01",
                    "time": "2024-10-09T14:49:00Z",
                    "alert_type": "breadth_signal"
                }
            '''

send_message(message)