from machine import Pin
import time
import network
import socket
from time import sleep
import asyncio
import urequest2
import urequests
import uselect
import os
import sys

# No-IP DDNS credentials and hostname
USERNAME = "marcelomecozzi"
PASSWORD = "MarceloPiso4"
HOSTNAME = "bombapiso4.ddns.net" # Replace with your actual No-IP hostname

# No-IP update URL
#NOIP_UPDATE_URL = f"http://{USERNAME}:{PASSWORD}@dynupdate.no-ip.com/nic/update?hostname={HOSTNAME}&myip=181.165.66.173"

public_ip = None
storedPublicIp = None
filename = "publicip.txt"
s = None
# Define the GPIO pin
relay_pin = Pin(4, Pin.OUT)

wifi_ssid = "WiFiDepto 2.4"
wifi_password = "pasapalabra"

sta_if = None

def base64_encode(data):
    """
    Encodes bytes-like data into a Base64 string.
    """
    base64_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    encoded_bytes = bytearray()
    padding_count = 0

    # Process data in 3-byte chunks
    for i in range(0, len(data), 3):
        chunk = data[i:i+3]
        
        # Combine up to 3 bytes into a 24-bit integer
        val = 0
        num_bytes = len(chunk)
        for j in range(num_bytes):
            #print(chunk[j], (8 * (2 - j)), int(ord(chunk[j])) << (8 * (2 - j)) )
            val |= ord(chunk[j]) << (8 * (2 - j))

        # Extract 6-bit chunks and map to Base64 characters
        for k in range(4):
            if k < num_bytes + 1: # Handle padding for partial chunks
                index = (val >> (6 * (3 - k))) & 0x3F
                encoded_bytes.append(ord(base64_chars[index]))
            else:
                encoded_bytes.append(ord('='))
                padding_count += 1
    
    return encoded_bytes.decode('ascii') # Return as an ASCII string

def connect_to_wifi(ssid, password):
    global sta_if
    sta_if = network.WLAN(network.STA_IF)
    if sta_if.isconnected():
        sta_if.disconnect()
    
    if not sta_if.isconnected():
        print("Connecting to WiFi...")
        host = 'bomba'
        sta_if.active(True)
        sta_if.config(hostname=host)
        sta_if.config(dhcp_hostname=host) # Set your desired hostname here
        network.hostname(host)
        
        while not sta_if.isconnected():
            try:
                sta_if.connect(ssid, password)
                break
            except OSError as e:
                print(f"Error connecting to {ssid}: {e}")
            time.sleep(10)
            
        while not sta_if.isconnected():
            time.sleep(1)
            
        # Get the status information
        
        #print(f"status: {status} ")
        # Extract and print signal strength
        #if status == 3: # 3 indicates connected
            # The following line is an example; the actual key/index might be different
            # Consult the specific documentation for your board and firmware.
        signal_strength = sta_if.status('rssi')
        print(f"Signal Strength: {signal_strength} dBm")
        #else:
            #print("Not connected to a Wi-Fi network.")
            
    print("Connected to WiFi!")
    print("Network configuration:", sta_if.ifconfig())
    print(f"Hostname: {network.hostname()}")
  
def update_noip_ddns():
    """
    Sends an update request to No-IP's DDNS server.
    """
    #print (f"{USERNAME}:{PASSWORD}")
    auth =  base64_encode(f"{USERNAME}:{PASSWORD}")

    try:
        header = {
            "Authorization": f"Basic {auth}"
        }
        NOIP_UPDATE_URL = f"http://dynupdate.no-ip.com/nic/update?hostname={HOSTNAME}&myip={public_ip}"
        print(NOIP_UPDATE_URL, header)
        response = urequest2.urlopen(NOIP_UPDATE_URL , headers = header)
        #response = urequest2.urlopen(NOIP_UPDATE_URL)
        print(response)
#         if response == 200:
#             print(f"No-IP update successful: {response.text}")
#         else:
#             print(f"No-IP update failed with status code {response.status_code}: {response.text}")
    except OSError as e:
        print(f"Error during No-IP update: {e}")


def web_page():
    """Generates the HTML page for the web server."""
    pin_state = "ON" if relay_pin.value() else "OFF"
    #print (pin_state)
    pin_state_text = "ENCENDIDO" if pin_state == "ON" else "APAGADO"
    
    html = f"""
    <!DOCTYPE html>
    <html>
        <script>
            //alert(window.location.href)
            if(window.location.href.indexOf('/o') > 0)
                window.location.href = '/'
            //history.replaceState("","/")
        </script>
        <head>
            <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate" />
            <meta http-equiv="Pragma" content="no-cache" />
            <meta http-equiv="Expires" content="0" />
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <title>Bomba 4to. Piso</title>
            <style>
                body {{ font-family: Arial, sans-serif; text-align: center; }}
                .submit {{
                    border: none;
                    color: white;
                    padding: 15px 32px;
                    text-align: center;
                    text-decoration: none;
                    display: inline-block;
                    font-size: 30px;
                    margin: 4px 2px;
                    cursor: pointer;
                    border-radius: 8px;
                    font-color: white;
                    font-weight: bold;
                    width: 250px;
                    height: 150px;
                }}
            </style>
        </head>
        <body>
            <h1>Bomba 4to. Piso</h1>
            <h2>Control de encendido</h2>
            <p>Estado actual de la Bomba: <strong style="font-size: 20px; """ + ("background-color:green; " if pin_state == "ON" else " background-color:red; ") + """ color: white">""" + pin_state_text + """</strong></p>
            <form action="/on?random=""" + str(time.time()) + """" onsubmit="disable_me(event)">
                <input id="on" type="submit" value="Prender&#x000A;Bomba" """ + ("disabled style='background-color:gray; cursor: not-allowed;' " if pin_state == "ON" else " style='background-color:green' ") + """ class='submit' />
            </form>
            </br>
            <form action="/off?random=""" + str(time.time()) + """" onsubmit="disable_me(event)">
                <input id="off" type="submit" value="Apagar&#x000A;Bomba" """ + ("disabled style='background-color:gray; cursor: not-allowed;' " if pin_state == "OFF" else " style='background-color:red' ") + """ class='submit' />
            </form>
            <script>
            function disable_me(e) {
                document.getElementById('on').disabled = true;
                document.getElementById('off').disabled = true;
                //alert(document.getElementById('off').disabled)
                //alert(document.getElementById('on').disabled)
            }
            </script>
        </body>
    </html>
    """
    return html

def serve_requests(connection):
    try:
        """Handles an incoming HTTP connection."""
        request = connection.recv(2048).decode('utf-8')
        #print('Request:', request)
            
        # Check for /on or /off in the request
        if '/on' in request:
            print("turning on")
            relay_pin.value(1) # Turn LED on
            sleep(1)
        elif '/off' in request:
            print("turning off")
            relay_pin.value(0) # Turn LED off
            sleep(1)
        
        if "favicon" in request:
            response = "HTTP/1.1 204 No Content\r\n"
        else:
            response = 'HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n' + web_page()
            
        #print(response)
        connection.send(response)
        connection.close()
    except Exception as e:
        #exc_type, exc_value, exc_trace = sys.exc_info()
        print ("Error serving request", e)

server = asyncio.get_event_loop()

# Main loop to accept connections
def run_server():
    global s
    
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(('', 8080))
        except:
            pass
            
        s.listen(1)
        #s.setblocking(False)
        print("Web server listening on port 8080...", s)
    except OSError as e:
        print("Error starting web server.", e)
    
def monitor_connections():
    global s
    global public_ip
    print("monitor_connections")
    rerun_server = False
    while True:
        try:
            current_public_ip = get_public_ip()
            print (current_public_ip, storedPublicIp)
            
            if current_public_ip != None and storedPublicIp != public_ip:
                public_ip = current_public_ip
                update_noip_ddns()
                if storedPublicIp == None or storedPublicIp != public_ip:
                    store_public_ip()
        except Exception as e:
            #exc_type, exc_value, exc_trace = sys.exc_info()
            print ("Error checking public ip", e.args[0] )#, exc_type, exc_value, exc_trace)

        try:
            #s.settimeout(60*60)
            s.settimeout(10*60)
            client_socket, client_address = s.accept()
            print(f"New connection from {client_address}")
            serve_requests(client_socket)
        except OSError as e:
            #exc_type, exc_value, exc_trace = sys.exc_info()
            if e.args[0] == errno.ETIMEDOUT:
                print("Socket accept timed out.")
            else:
                print("Error handling client connection:",  e) #, exc_type, exc_value, exc_trace)
                
                try:
                    s.close()
                except:
                    pass
                
                rerun_server = True
        
        try:
            if sta_if.isconnected():
                signal_strength = sta_if.status('rssi')
                print(f"Signal Strength: {signal_strength} dBm")
            else:
                print(f"WiFi has been disconnected.")
                connect_to_wifi(wifi_ssid, wifi_password)
        except:
            pass
                
        if sta_if.isconnected():
            if rerun_server:
                rerun_server = False
                run_server()
        
def get_public_ip():
    try:
        r = urequests.get('http://checkip.amazonaws.com')
        ip = r.text.strip()
        print('Public IP address:', ip)
        r.close()
        return ip
    except Exception as e:
        print("Could not get public IP:", e)
        return None

# Example usage
def load_stored_public_ip():
    global storedPublicIp
    
    try:
        with open(filename, "r") as f:
            storedPublicIp = f.readline()
            print("Stored public ip", storedPublicIp)
    except OSError as e:
        print(f"No file: {e}")
        
def store_public_ip():
    global storedPublicIp
    
    try:
        with open(filename, "w") as f:
            f.write(public_ip)
            storedPublicIp = public_ip
            print("Writing public ip", public_ip) 
    except OSError as e:
        print(f"Error writing file: {e}")

load_stored_public_ip()
connect_to_wifi(wifi_ssid, wifi_password)
run_server()

#asyncio.run(monitor_connections())
server.create_task(monitor_connections())

server.run_forever()
# Loop indefinitely to toggle the LED
# while True:
#     relay_pin.value(1)  # Turn the LED on (set pin high)
#     time.sleep(5)   # Wait for 0.5 seconds
#     relay_pin.value(0)  # Turn the LED off (set pin low)
#     time.sleep(5)   # Wait for 0.5 seconds
