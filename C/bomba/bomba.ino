#include <WiFi.h>
#include <NetworkClient.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include "FS.h" // Required for filesystem operations
#include "LittleFS.h" // Required for LittleFS
#include <EasyDDNS.h>


const char *ssid = "WiFiDepto 2.4";
const char *password = "pasapalabra";

const char *USERNAME = "marcelomecozzi";
const char *PASSWORD = "MarceloPiso4";
const char *HOSTNAME = "bombapiso4.ddns.net";

#define FORMAT_LITTLEFS_IF_FAILED true

WebServer server(8080);

const int ledPin = 8;
const int relayPin = 4;
const int buttonPin = 3;

String indexTemplate = "";
static String lastRandom = "";

// --- TIME CONSTANTS (in milliseconds) ---
const unsigned long DEBOUNCE_TIME_MS = 50;  // Debounce time to filter switch bounce
const unsigned long HOLD_TIME_MS = 3000; // Required press duration (3 seconds)

// Timer setup values
const uint32_t TIMER_FREQUENCY_HZ = 100;    // Sets the timer to tick 100 times per second (every 10ms)
const uint64_t ALARM_VALUE_TICKS = 1;       // Alarm triggers after 1 tick of the 100Hz timer
const uint64_t RELOAD_COUNT_UNLIMITED = 0;  // Set reload count to 0 for continuous (unlimited) alarms


// --- VOLATILE GLOBAL STATE VARIABLES ---
// Variables modified inside an Interrupt Service Routine (ISR) must be volatile.
volatile unsigned long last_valid_interrupt_time = 0; // Stores time of the last accepted button state change (for debouncing)
volatile unsigned long press_start_time = 0;          // Stores the time when a valid press began
volatile bool is_button_pressed = false;             // Current state of the button (after debouncing)
volatile bool action_fired = false;                  // Flag to ensure the action is triggered only once per long press

// --- NATIVE ESP32 TIMER OBJECTS ---
hw_timer_t * timer = NULL; // Pointer to the hardware timer structure
portMUX_TYPE timerMux = portMUX_INITIALIZER_UNLOCKED; // Mutex for critical sections

// --- FUNCTION PROTOTYPES ---
void handleButtonChange();
void checkLongPress();

void handleRoot() {
  //Serial.print("handleRoot");
  //String indexContent;
  String operation = "";
  String random = "";
  if(server.hasArg("op"))
  {
    operation = server.arg("op");
    if (server.hasArg("rnd"))
      random = server.arg("rnd");

    Serial.println("params ");
    Serial.println(operation);
    Serial.println(random);
    Serial.println("last random ");
    Serial.println(lastRandom);

    if (lastRandom == random)
    {
      //ignore operation
      operation = "";
    }
    else
    {
      if (operation == "on")
        digitalWrite(relayPin, 1);
      else
        digitalWrite(relayPin, 0);

      lastRandom = random;
    }
  }

  String relayValue = String(digitalRead(relayPin));
  String indexContent = String(indexTemplate);
  indexContent.replace("[[RELAY_STATE]]", relayValue);
  Serial.print("indexContent length ");
  Serial.print(indexContent.length());

  server.send(200, "text/html", indexContent);
  digitalWrite(ledPin, !digitalRead(relayPin));
}

void handleNotFound() {
  Serial.print("handleNotFound");
  //digitalWrite(ledPin, 1);
  String message = "File Not Found\n\n";
  message += "URI: ";
  message += server.uri();
  message += "\nMethod: ";
  message += (server.method() == HTTP_GET) ? "GET" : "POST";
  message += "\nArguments: ";
  message += server.args();
  message += "\n";

  for (uint8_t i = 0; i < server.args(); i++) {
    message += " " + server.argName(i) + ": " + server.arg(i) + "\n";
  }

  server.send(404, "text/plain", message);
  //digitalWrite(ledPin, 0);
}
volatile unsigned long lastInterruptTimeRising = 0;
volatile unsigned long lastInterruptTimeRisingRecorded = 0;
volatile unsigned long lastInterruptTimeFalling = 0;
const unsigned long debounceDelay = 500; // milliseconds

// -----------------------------------------------------------
// INTERRUPT SERVICE ROUTINES (ISRs)
// -----------------------------------------------------------

void IRAM_ATTR handleButtonChange() { 
  unsigned long current_time = millis();
  
  // --- Debouncing Check ---
  if (current_time - last_valid_interrupt_time < DEBOUNCE_TIME_MS) {
    return;
  }
  last_valid_interrupt_time = current_time;

  // Since we attached to FALLING, we only see the press.
  portENTER_CRITICAL_ISR(&timerMux);
  
  is_button_pressed = true; // Set flag
  press_start_time = current_time; 
  action_fired = false;      
  
  portEXIT_CRITICAL_ISR(&timerMux);
}

void IRAM_ATTR checkLongPressISR() {
  
  portENTER_CRITICAL_ISR(&timerMux);
  
  // Check the physical state of the button pin
  bool pin_is_low = (digitalRead(buttonPin) == LOW);

  // A. Correct the internal state if the button was released (Missed RISING edge)
  if (is_button_pressed && !pin_is_low) {
    // If the flag is set but the pin is HIGH, the press has ended.
    is_button_pressed = false; 
  }
  
  // B. Check for long press only if the flag is set AND the pin is currently low.
  if (is_button_pressed && pin_is_low) {
    unsigned long current_time = millis();
    
    // Check if the hold time has elapsed AND the action hasn't been fired yet
    if (!action_fired && (current_time - press_start_time >= HOLD_TIME_MS)) {
      
      // ** TOGGLE ACTION LOGIC **
      bool new_state = !digitalRead(relayPin);
      
      digitalWrite(relayPin, new_state); 
      digitalWrite(ledPin, !new_state); // Assuming the LED should mirror the relay state (HIGH/LOW)

      action_fired = true; // Prevent re-triggering during this press
    }
  } 
  
  portEXIT_CRITICAL_ISR(&timerMux);
}

void setup(void) {
  Serial.begin(115200);
  Serial.println("INIT");
  // Initialize LittleFS
  if (!LittleFS.begin(FORMAT_LITTLEFS_IF_FAILED)) {
    Serial.println("LittleFS Mount Failed");
    return;
  }
  
  Serial.println("LittleFS mounted successfully");
  //listDir(LittleFS, "/", 3);
  

  /*
  // Open a file for reading
  File file = LittleFS.open("/template.html", "r"); // "r" for read mode

  if (!file) {
    Serial.println("Failed to open file for reading");
    return;
  }
  
  Serial.println("File opened successfully. Reading content:");
  */
  // Read content from the file
  indexTemplate = readFile("/template.html");
  Serial.print("/template.html ");
  Serial.println(indexTemplate.length());
  //while (file.available()) {
  //  Serial.println(file.read());
  //}

  // Close the file
  //file.close();

  pinMode(ledPin, OUTPUT);
  pinMode(relayPin, OUTPUT);
  digitalWrite(ledPin, !digitalRead(relayPin));
  //digitalWrite(ledPin, 0);
  Serial.begin(115200);
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  //Serial.println("");

  // Wait for connection
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("");
  Serial.print("Connected to ");
  Serial.println(ssid);
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());

  if (MDNS.begin("esp32")) {
    Serial.println("MDNS responder started");
  }

  EasyDDNS.service("noip");
  EasyDDNS.client(HOSTNAME, USERNAME, PASSWORD);
  
  // Get Notified when your IP changes
  EasyDDNS.onUpdate([&](const char* oldIP, const char* newIP){
    Serial.print("EasyDDNS - IP Change Detected: ");
    Serial.println(newIP);
  });

  server.on("/", handleRoot);
  
  server.onNotFound(handleNotFound);
  server.begin();
  Serial.println("HTTP server started");

  // Assuming a pull-up resistor is used (either internal or external), 
  // so the pin is HIGH when released and LOW when pressed.
  pinMode(buttonPin, INPUT_PULLUP);

  // Configure Timer 0 with a frequency of 1,000,000 Hz (1 MHz),
  // which results in a tick every 1 microsecond.
  timer = timerBegin(1000000);

  // Attach the ISR function (two arguments, as per your compiler)
  timerAttachInterrupt(timer, &checkLongPressISR); 

  // Set the alarm to fire every 1,000,000 counts (1 second).
  // The 'autoreload' parameter is now the second-to-last argument.
  timerAlarm(timer, 1000000, true, 0);

  Serial.println("timerAttachInterrupt");

  // The timerAlarm call in both cases should have enabled the alarm.


  // 2. External Interrupt Configuration (for the Button)
  // Attach the interrupt to the button pin. We use CHANGE to detect both press (FALLING) and release (RISING).
  attachInterrupt(digitalPinToInterrupt(buttonPin), handleButtonChange, CHANGE); 

}

void loop(void) {
  //Serial.print("looop");
  server.handleClient();
  delay(2);  //allow the cpu to switch to other tasks
  EasyDDNS.update(10 * 60 * 1000);
}

String readFile(const char* path) {
  File file = LittleFS.open(path, "r");
  if (!file) {
    Serial.printf("Failed to open file %s for reading\n", path);
    return "";
  }

  String content = file.readString(); // Reads the entire file content into a String
  file.close();
  return content;
}

void listDir(fs::FS &fs, const char *dirname, uint8_t levels) {
  Serial.printf("Listing directory: %s\r\n", dirname);

  File root = fs.open(dirname);
  if (!root) {
    Serial.println("- failed to open directory");
    return;
  }
  if (!root.isDirectory()) {
    Serial.println(" - not a directory");
    return;
  }

  File file = root.openNextFile();
  while (file) {
    if (file.isDirectory()) {
      Serial.print("  DIR : ");
      Serial.println(file.name());
      if (levels) {
        listDir(fs, file.path(), levels - 1);
      }
    } else {
      Serial.print("  FILE: ");
      Serial.print(file.name());
      Serial.print("\tSIZE: ");
      Serial.println(file.size());
    }
    file = root.openNextFile();
  }
}


