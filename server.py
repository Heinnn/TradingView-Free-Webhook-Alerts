import socket
import json
import signal
import gspread
from src import log, config
import MetaTrader5 as mt5
import time
import threading
from rich import print as cprint
from rich import traceback

traceback.install()

# --------------------------------- Config ---------------------------------
sheet_url = config.get("sheet_url")
cell_order_direction = config.get("cell_order_direction")

user_id = config.get("user_id")
password = config.get("password")
server = config.get("server")

trade_direction = None

# --------------------------------- GOOGLE SHEET ---------------------------------

def get_cell_value(sheet_url, cell):
    global trade_direction
    """Fetches the trade direction from Google Sheets."""
    try:
        gc = gspread.service_account(filename='sheetapi-437814-73f30fd1a6f2.json')
        sheet = gc.open_by_url(sheet_url)
        worksheet = sheet.get_worksheet(0)
        trade_direction = worksheet.acell(cell).value
        return trade_direction
    except gspread.exceptions.GSpreadException as e:
        log.warning(f"Cannot GET TREND from SHEET: {e}")
        return None

# --------------------------------- MT5 Management---------------------------------

def mt5_login(user_id, password, server, max_retry=3):
    global mt5
    """Logs into MetaTrader 5 terminal with retries."""
    for attempt in range(1, max_retry + 1):
        if mt5.initialize(login=int(user_id), password=password, server=server):
            log.info(f"Account {user_id} Login successful.")
            return True
        else:
            log.warning(f"Login attempt {attempt}/{max_retry} failed. Retrying in 60 seconds...")
            time.sleep(60)
    log.error("Maximum login attempts reached. Unable to connect.")
    return False

def get_account_info():
    global mt5
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
    global mt5
    """Checks if algorithmic trading is enabled and logs the status."""
    terminal_info = mt5.terminal_info()
    if terminal_info is None:
        log.error("Failed to retrieve terminal info.")
        return False
    algo_trading_allowed = terminal_info.trade_allowed
    log.ok("Algorithmic trading is allowed." if algo_trading_allowed else "Algorithmic trading is NOT allowed.")
    return algo_trading_allowed

def get_current_info(sheet_url, cell):
    global mt5
    
    trade_direction = get_cell_value(sheet_url, cell)
    acc_inf = mt5.account_info()
    orders = mt5.orders_total()
    position = mt5.positions_total()
    log.info(f"TREND: {trade_direction} , AC: {acc_inf[0]} , tOrder : {orders} , tPosition: {position}")

def get_info(symbol):
    '''https://www.mql5.com/en/docs/integration/python_metatrader5/mt5symbolinfo_py
    '''
    # get symbol properties
    info=mt5.symbol_info(symbol)
    return info

def open_trade(action, symbol, lot, sl, tp, deviation):
    global mt5
    '''https://www.mql5.com/en/docs/integration/python_metatrader5/mt5ordersend_py
    '''
    # prepare the buy request structure
    symbol_info = get_info(symbol)
    
    if symbol_info is None:
        print(f"Failed to get symbol info for {symbol}")
        return None, None

    # Determine trade type and price
    if action == 'LONG':
        trade_type = mt5.ORDER_TYPE_BUY
        price = mt5.symbol_info_tick(symbol).ask
    elif action == 'SHORT':
        trade_type = mt5.ORDER_TYPE_SELL
        price = mt5.symbol_info_tick(symbol).bid
    else:
        print(f"Invalid action: {action}")
        return None, None

    # Calculate the point value for the symbol
    point = symbol_info.point

    # Prepare the base request object
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": trade_type,
        "price": price,
        "deviation": deviation,
        "type_time": mt5.ORDER_TIME_GTC,  # Good till canceled
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }

    # Include 'sl' and 'tp' in the request only if they are provided
    if sl:
        request["sl"] = float(sl)
    if tp:
        request["tp"] = float(tp)

    # Send a trading request
    result = mt5.order_send(request)
    return result, request

def close_trade(action, buy_request, result, deviation):
    '''https://www.mql5.com/en/docs/integration/python_metatrader5/mt5ordersend_py
    '''
    # create a close request
    symbol = buy_request['symbol']
    if action == 'buy':
        trade_type = mt5.ORDER_TYPE_BUY
        price = mt5.symbol_info_tick(symbol).ask
    elif action =='sell':
        trade_type = mt5.ORDER_TYPE_SELL
        price = mt5.symbol_info_tick(symbol).bid
    position_id=result.order
    lot = buy_request['volume']

    close_request={
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": trade_type,
        "position": position_id,
        "price": price,
        "deviation": deviation,
        # "magic": ea_magic_number,
        "comment": "python script close",
        "type_time": mt5.ORDER_TIME_GTC, # good till cancelled
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }
    # send a close request
    result=mt5.order_send(close_request)
    
# --------------------------------- Order Management---------------------------------

def message_reader(message):
    """Parses the JSON formatted message into trade parameters.
        message = {
                    "action": "SHORT",
                    "ticker": "XAUUSD",
                    "price": "2607.52",
                    "tp": "",
                    "sl": "2620.01",
                    "time": "2024-10-09T14:37:00Z",
                    "alert_type": "breadth_signal"
                }
    """
    
    try:
        # Parse the JSON message
        data = json.loads(message)
        
        # Extract fields with error checking for required fields
        action = data.get("action")
        symbol = data.get("ticker")
        sl = data.get("sl")
        tp = data.get("tp", None)  # Default to None if tp is not provided

        # Check for missing required fields
        if not all([action, symbol, sl]):
            log.error("Missing one or more required fields in the message.")
            return None, None, None, None

        # Return the extracted values, tp can be None
        return str(action), str(symbol), float(sl), tp
        
    except json.JSONDecodeError:
        log.error("Failed to decode JSON. Please check the message format.")
        return None, None, None, None
    

def handle_client(client_socket, client_address):
    global mt5
    
    """Handles a single client connection."""
    try:
        log.info(f"Connected by {client_address}")
        while True:
            message = client_socket.recv(1024).decode('utf-8')
            if not message:
                log.warning(f"Connection closed by {client_address}")
                break

            log.info(f"Received message from {client_address}: {message}")
            
            # Parse the message
            action, symbol, sl, tp = message_reader(message)
            if None in (action, symbol, sl):
                client_socket.sendall("Invalid message format.".encode('utf-8'))
                continue
            # Check Bias weather to trade
            if trade_direction != action:
                log.warning(f"BiasTrend: {trade_direction} & AlertAction: {action} Which Opposite!")
                continue
            
            lot = 0.1
            # Retry logic
            for attempt in range(3):  # Retry up to 3 times
                result, req = open_trade(action, symbol, lot, sl, tp=None, deviation=10)
                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    response = "Order executed successfully."
                    client_socket.sendall(response.encode('utf-8'))
                    log.ok(f"Order successful")
                    break
                else:
                    log.error(f"Trade failed with error code {result.retcode}. Retrying... [{attempt + 1}/3]")
                    time.sleep(2)  # Wait a bit before retrying
            else:
                response = f"Trade failed after 3 attempts. Error code: {result.retcode}"
                client_socket.sendall(response.encode('utf-8'))
                log.error(response)

    except Exception as e:
        log.error(f"Error handling client {client_address}: {e}")
    finally:
        client_socket.close()
        log.info(f"Connection with {client_address} closed.")

def run_server(host='0.0.0.0', port=65432):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((host, port))
        server_socket.listen()
        server_socket.settimeout(1)  # Non-blocking with timeout
        log.info(f"Server listening on {host}:{port}")

        while not termination_flag.is_set():
            try:
                client_socket, client_address = server_socket.accept()
                client_thread = threading.Thread(target=handle_client, args=(client_socket, client_address))
                client_thread.start()
            except socket.timeout:
                continue  # Loop back to check termination_flag
            except Exception as e:
                log.error(f"Error accepting connections: {e}")


termination_flag = threading.Event()

# Signal handler for Ctrl+C
def signal_handler(sig, frame):
    log.info("Shutdown requested by user (Ctrl+C).")
    termination_flag.set()

# Attach the signal handler
signal.signal(signal.SIGINT, signal_handler)

# Update periodic_fetch_info for frequent checks
def periodic_fetch_info(sheet_url, cell, interval=100):
    while not termination_flag.is_set():
        try:
            get_current_info(sheet_url, cell)
        except Exception as e:
            log.error(f"Error in periodic_fetch_info: {e}")
        finally:
            # Check every second to allow for quicker shutdown
            for _ in range(interval):
                if termination_flag.is_set():
                    break
                time.sleep(1)

# Update the main script
if __name__ == "__main__":
    if mt5_login(user_id, password, server):
        get_account_info()
        is_algo_trading_enabled()
    else:
        log.error("MT5 login failed. Exiting application.")
        sys.exit(1)

    # Start periodic fetch info in a non-daemon thread
    t = threading.Thread(target=periodic_fetch_info, args=(sheet_url, cell_order_direction))
    t.start()

    try:
        run_server()
    except Exception as e:
        log.error(f"Unexpected error: {e}")
    finally:
        termination_flag.set()  # Trigger shutdown for other threads
        t.join()
        mt5.shutdown()
        log.info("MT5 shutdown completed.")
        log.info("Application terminated.")