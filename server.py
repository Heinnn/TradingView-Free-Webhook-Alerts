import socket
import gspread
from src import log
import MetaTrader5 as mt5
import time

def initialize_globals():
    """Initializes global settings like sheet URL and cell to be read."""
    sheet_url = "https://docs.google.com/spreadsheets/d/1nxkOaLEdKM0IKk7gAWWnGJiH-2nuaFpBqgq2duEnpZA/"
    cell = "A1"
    return sheet_url, cell

def get_trade_direction(sheet_url, cell):
    """Fetches the trade direction from Google Sheets."""
    try:
        gc = gspread.service_account(filename='sheetapi-437814-11921ab7b635.json')
        sheet = gc.open_by_url(sheet_url)
        worksheet = sheet.get_worksheet(0)
        trade_direction = worksheet.acell(cell).value
        log.info(f"CURRENT TREND: {trade_direction}")
        return trade_direction
    except gspread.exceptions.GSpreadException as e:
        log.warning(f"Cannot GET TREND from SHEET: {e}")
        return None

def mt5_login(terminal_path, user_id, password, server, max_retry=3):
    """Logs into MetaTrader 5 terminal with retries."""
    for attempt in range(1, max_retry + 1):
        if mt5.initialize(path=terminal_path, login=int(user_id), password=password, server=server):
            log.info(f"Account {user_id} Login successful.")
            return True
        else:
            log.warning(f"Login attempt {attempt}/{max_retry} failed. Retrying in 60 seconds...")
            time.sleep(60)
    log.error("Maximum login attempts reached. Unable to connect.")
    return False

def get_account_info():
    """Retrieves and logs account information from MetaTrader 5."""
    account_info = mt5.account_info()
    if account_info is None:
        log.error("Failed to retrieve account info.")
        return None
    account_info_dict = account_info._asdict()
    for prop, value in account_info_dict.items():
        log.info(f"{prop} = {value}")
    return account_info_dict

def is_algo_trading_enabled():
    """Checks if algorithmic trading is enabled and logs the status."""
    terminal_info = mt5.terminal_info()
    if terminal_info is None:
        log.error("Failed to retrieve terminal info.")
        return False
    algo_trading_allowed = terminal_info.trade_allowed
    log.info("Algorithmic trading is allowed." if algo_trading_allowed else "Algorithmic trading is NOT allowed.")
    return algo_trading_allowed

def run_server(host='0.0.0.0', port=65432):
    """Runs a TCP server that listens for incoming connections and handles them."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((host, port))
        server_socket.listen()
        log.info(f"Server listening on {host}:{port}")

        while True:
            try:
                client_socket, client_address = server_socket.accept()
                with client_socket:
                    log.info(f"Connected by {client_address}")
                    message = client_socket.recv(1024).decode('utf-8')
                    if not message:
                        log.warning(f"Connection closed by {client_address}")
                        continue
                    log.info(f"Received message from {client_address}: {message}")
                    
                    response = 'Message received'
                    client_socket.sendall(response.encode('utf-8'))
                    log.info(f"Sent response to {client_address}: {response}")
            except Exception as e:
                log.error(f"Error occurred: {e}")


if __name__ == "__main__":
    terminal_path = "path_to_terminal.exe"
    user_id = "10004045529"
    password = "17142hine"
    server = "MetaQuotes-Demo"

    if mt5_login(terminal_path, user_id, password, server):
        get_account_info()
        is_algo_trading_enabled()

    sheet_url, cell = initialize_globals()
    get_trade_direction(sheet_url, cell)

    # RUN server
    run_server()

    mt5.shutdown()
