import socket

def run_server(host='0.0.0.0', port=65432):
    # Create a socket object
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((host, port))
        server_socket.listen()
        print(f"Server listening on {host}:{port}")

        while True:
            try:
                # Wait for a connection
                client_socket, client_address = server_socket.accept()
                with client_socket:
                    print(f"Connected by {client_address}")
                    
                    # Receive message from client
                    message = client_socket.recv(1024).decode('utf-8')
                    if not message:
                        print(f"Connection closed by {client_address}")
                        continue
                    print(f"Received message from {client_address}: {message}")

                    # Send a response back to the client
                    response = 'Message received'
                    client_socket.sendall(response.encode('utf-8'))
                    print(f"Sent response to {client_address}: {response}")
            except Exception as e:
                print(f"Error occurred: {e}")

if __name__ == "__main__":
    run_server()
