// Código para conexión de un ESP32 con un adc, reloj en tiempo real y módulo de memoria 
// para generar una lectura de una galga extensiométrica
// Modificado para enviar datos por WiFi a Google Sheets
// Estructura base generada por GeminiAI
// Código de lectura y guardado de microSD tomado de Wemos:
// https://github.com/wemos/D1_mini_Examples/blob/master/examples/04.Shields/Micro_SD_Shield/Datalogger/Datalogger.ino
// Correción de Errores con Deepseek.AI

// Código para conexión de un ESP32 con ADC, RTC DS1302 y envío de datos a Google Sheets
// Basado en el código original de InaFinal.ino
// Modificado para enviar datos por WiFi a Google Sheets

#include <Wire.h>
#include <Adafruit_ADS1X15.h>
#include <RtcDS1302.h>
#include <WiFi.h>
#include <HTTPClient.h>

// ================= CONFIG WIFI =================
const char* WIFI_SSID = "Bastos";           // Cambia esto
const char* WIFI_PASSWORD = "Bastos05";      // Cambia esto

// ================= CONFIG GOOGLE SHEETS =================
// Instrucciones para obtener este URL:
// 1. Abre Google Sheets y crea una nueva hoja
// 2. Ve a Extensiones > Apps Script
// 3. Copia el código de Google Apps Script que te proporcionaré
// 4. Publica como Web App y copia el URL aquí
String GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbxRj6wk9bBcg3S6NYa_kP_psJUPH0M5yQEDeIoEhElHASDxtMNxmQzsaJI85y3q_fH8AA/exec";

// ================= CONFIG RTC DS1302 =================
#define DS1302_RST_PIN 14
#define DS1302_DAT_PIN 12
#define DS1302_CLK_PIN 13

// Descomentar siguiente línea para configurar el reloj con fecha actual
// #define CONFIGURAR_RTC_PRIMERA_VEZ 

ThreeWire myWire(DS1302_DAT_PIN, DS1302_CLK_PIN, DS1302_RST_PIN);
RtcDS1302<ThreeWire> Rtc(myWire);

// ================= CONFIG STRAIN =================
Adafruit_ADS1115 ads;

const float FACTOR_CAL = 433.46f;
const float V_EXC = 5.0f;

const uint8_t PIN_BOTON_STOP = 16;
const uint8_t PIN_BOTON_TARE = 17;
const uint8_t PIN_LED = 4;

bool isMeasuring = false;  // Comienza pausado hasta conectar WiFi
bool needsTare = true;
float offsetStrain = 0.0f;

const unsigned long DEBOUNCE_MS = 50;
const unsigned long SAMPLE_INTERVAL_MS = 1000;  // 1 segundo
unsigned long lastSampleTime = 0;
unsigned long sampleCount = 0;

unsigned long lastDebounceTime = 0;
int lastButtonReading = HIGH;
unsigned long lastDebounceTimeTARE = 0;
int lastButtonReadingTARE = HIGH;

bool wifi_connected = false;

// ================= PROTOTIPOS DE FUNCIONES =================
void conectarWiFi();
void imprimirHoraActual();
String obtenerTimestamp();
void toggleMedicion();
void realizarTare();
float medirStrain();
float medirVoltaje();
void mostrarEnSerial(float comp, float bruto, float vdiff);
void enviarAGoogleSheets(float comp, float vdiff);
void handleButtonDebounce();
void handleButtonTare();
void checkSerialCommands();

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n\n========================================");
  Serial.println("  Sistema de Medición de Strain");
  Serial.println("  con Google Sheets");
  Serial.println("========================================\n");
  
  // Configuración de pines
  pinMode(PIN_BOTON_STOP, INPUT_PULLUP);
  pinMode(PIN_BOTON_TARE, INPUT_PULLUP);
  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_LED, LOW);

  // ==== I2C y ADS1115 ====
  Serial.println("Inicializando ADS1115...");
  Wire.begin(21, 23);
  if (!ads.begin(0x48)) {
    Serial.println("❌ Error inicializando ADS1115");
    while (1) {
      digitalWrite(PIN_LED, !digitalRead(PIN_LED));
      delay(200);
    }
  }
  ads.setGain(GAIN_SIXTEEN);
  Serial.println("✓ ADS1115 listo");
  
  // ==== DS1302 RTC ====
  Serial.println("Inicializando RTC DS1302...");
  Rtc.Begin();

  if (!Rtc.IsDateTimeValid()) {
    Serial.println("RTC: Hora NO válida o pila agotada.");
    if (Rtc.GetIsWriteProtected()) {
      Serial.println("RTC: Deshabilitando protección de escritura.");
      Rtc.SetIsWriteProtected(false);
    }
  }

  #ifdef CONFIGURAR_RTC_PRIMERA_VEZ
  Rtc.SetDateTime(RtcDateTime(__DATE__, __TIME__));
  Serial.println("✓ RTC configurado con hora de compilación.");
  #endif

  imprimirHoraActual();
  
  // ==== Conectar WiFi ====
  conectarWiFi();

  Serial.println("\n========================================");
  Serial.println("  Inicialización completa.");
  Serial.println("  Comandos: t=tare, s=start/stop");
  Serial.println("  Presiona 's' para comenzar a medir");
  Serial.println("========================================\n");
  
  // Parpadeo rápido para indicar listo
  for(int i = 0; i < 6; i++) {
    digitalWrite(PIN_LED, !digitalRead(PIN_LED));
    delay(100);
  }
  digitalWrite(PIN_LED, LOW);
}

void loop() {
  // Verificar conexión WiFi
  if (WiFi.status() != WL_CONNECTED) {
    wifi_connected = false;
    if (isMeasuring) {
      Serial.println("⚠ WiFi desconectado. Pausando medición...");
      isMeasuring = false;
      digitalWrite(PIN_LED, LOW);
    }
    conectarWiFi();
    return;
  }
  
  handleButtonDebounce();
  handleButtonTare();
  checkSerialCommands();

  unsigned long now = millis();
  if (isMeasuring && (now - lastSampleTime >= SAMPLE_INTERVAL_MS)) {
    lastSampleTime = now;

    float bruto = medirStrain();
    float comp = bruto - offsetStrain;
    float vdiff = medirVoltaje();

    mostrarEnSerial(comp, bruto, vdiff);
    enviarAGoogleSheets(comp, vdiff);
  }
}

// ================= FUNCIONES DE WIFI =================
void conectarWiFi() {
  Serial.print("Conectando a WiFi");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  
  int intentos = 0;
  while (WiFi.status() != WL_CONNECTED && intentos < 20) {
    delay(500);
    Serial.print(".");
    intentos++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n✓ WiFi conectado!");
    Serial.print("IP: ");
    Serial.println(WiFi.localIP());
    wifi_connected = true;
  } else {
    Serial.println("\n❌ No se pudo conectar a WiFi");
    Serial.println("Verifica SSID y contraseña");
    wifi_connected = false;
  }
}

// ================= FUNCIONES DE RTC DS1302 =================
void imprimirHoraActual() {
  if (!Rtc.IsDateTimeValid()) {
    Serial.println("Error obteniendo hora. RTC NO válido.");
    return;
  }
  RtcDateTime now = Rtc.GetDateTime();
  Serial.printf("Hora actual: %02d/%02d/%04d %02d:%02d:%02d\n",
                now.Day(), now.Month(), now.Year(),
                now.Hour(), now.Minute(), now.Second());
}

String obtenerTimestamp() {
  if (!Rtc.IsDateTimeValid()) {
    return "ERROR_TIME";
  }
  
  RtcDateTime now = Rtc.GetDateTime();
  char buffer[30];
  snprintf(buffer, sizeof(buffer), "%d/%d/%04d  %02d:%02d:%02d",
           now.Day(), now.Month(), now.Year(),
           now.Hour(), now.Minute(), now.Second());
  return String(buffer);
}

// ================= FUNCIÓN PARA ENVIAR A GOOGLE SHEETS =================
void enviarAGoogleSheets(float comp, float vdiff) {
  if (!wifi_connected) {
    Serial.println("⚠ No se puede enviar: WiFi no disponible");
    return;
  }
  
  if (!Rtc.IsDateTimeValid()) {
    Serial.println("⚠ No se puede enviar: RTC no válido");
    return;
  }
  
  HTTPClient http;
  
  // Construir URL con parámetros
  String url = GOOGLE_SCRIPT_URL;
  url += "?timestamp=" + obtenerTimestamp();
  url += "&record=" + String(sampleCount);
  url += "&strain=" + String(comp, 4);
  url += "&voltage=" + String(vdiff, 6);
  
  // Reemplazar espacios por %20 en la URL
  url.replace(" ", "%20");
  
  http.begin(url);
  http.setFollowRedirects(HTTPC_STRICT_FOLLOW_REDIRECTS);
  
  int httpCode = http.GET();
  
  if (httpCode > 0) {
    if (httpCode == HTTP_CODE_OK || httpCode == HTTP_CODE_MOVED_PERMANENTLY) {
      String response = http.getString();
      if (sampleCount % 10 == 0) {  // Mostrar cada 10 muestras
        Serial.println("✓ Datos enviados a Google Sheets");
      }
    } else {
      Serial.printf("⚠ Error HTTP: %d\n", httpCode);
    }
  } else {
    Serial.printf("❌ Error de conexión: %s\n", http.errorToString(httpCode).c_str());
  }
  
  http.end();
}

// ================= FUNCIONES AUXILIARES =================
void checkSerialCommands() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == 't' || c == 'T') realizarTare();
    else if (c == 's' || c == 'S') toggleMedicion();
    else if (c == 'o' || c == 'O') {
      Serial.print("Offset actual: ");
      Serial.print(offsetStrain, 4);
      Serial.println(" µε");
    } else if (c == 'h' || c == 'H') {
      imprimirHoraActual();
    } else if (c == 'w' || c == 'W') {
      Serial.print("WiFi: ");
      Serial.println(WiFi.status() == WL_CONNECTED ? "Conectado" : "Desconectado");
      if (WiFi.status() == WL_CONNECTED) {
        Serial.print("IP: ");
        Serial.println(WiFi.localIP());
      }
    } else if (c == '?') {
      Serial.println("\n===== COMANDOS DISPONIBLES =====");
      Serial.println("t: Realizar tare (calibrar a cero)");
      Serial.println("s: Start/Stop medición");
      Serial.println("o: Mostrar offset actual");
      Serial.println("h: Mostrar hora del RTC");
      Serial.println("w: Estado de WiFi");
      Serial.println("?: Mostrar esta ayuda");
      Serial.println("================================\n");
    }
  }
}

void handleButtonDebounce() {
  int reading = digitalRead(PIN_BOTON_STOP);
  
  if (reading != lastButtonReading) {
    lastDebounceTime = millis();
  }
  
  if ((millis() - lastDebounceTime) > DEBOUNCE_MS) {
    // Si el estado del botón es estable y cambió, detectar el flanco de bajada
    static int lastStableState = HIGH;
    
    if (reading != lastStableState) {
      lastStableState = reading;
      
      if (reading == LOW) {  // Flanco de bajada (botón presionado)
        toggleMedicion();
      }
    }
  }
  
  lastButtonReading = reading;
}

void handleButtonTare() {
  int reading = digitalRead(PIN_BOTON_TARE);
  if (reading != lastButtonReadingTARE) {
    lastDebounceTimeTARE = millis();
    lastButtonReadingTARE = reading;
  } else {
    if ((millis() - lastDebounceTimeTARE) > DEBOUNCE_MS) {
      if (reading == LOW) {
        realizarTare();
        while (digitalRead(PIN_BOTON_TARE) == LOW) delay(10);
      }
    }
  }
}

void toggleMedicion() {
  if (!wifi_connected) {
    Serial.println("❌ No se puede iniciar: WiFi no conectado");
    return;
  }
  
  if (!Rtc.IsDateTimeValid()) {
    Serial.println("❌ No se puede iniciar: RTC no válido");
    return;
  }
  
  isMeasuring = !isMeasuring;
  digitalWrite(PIN_LED, isMeasuring ? HIGH : LOW);
  
  if (isMeasuring) {
    sampleCount = 0;  // Reiniciar contador
    Serial.println("\n🟢 Medición INICIADA");
    Serial.println("Enviando datos cada segundo a Google Sheets...\n");
  } else {
    Serial.println("\n🔴 Medición PAUSADA");
    Serial.printf("Total de muestras tomadas: %lu\n\n", sampleCount);
  }
}

void realizarTare() {
  Serial.println("⚙ Realizando TARE...");
  const int N = 40;
  float s = 0.0f;
  for (int i = 0; i < N; ++i) {
    s += medirStrain();
    delay(25);
  }
  offsetStrain = s / N;
  needsTare = false;
  Serial.print("✓ TARE completo. Offset = ");
  Serial.print(offsetStrain, 4);
  Serial.println(" µε");
}

float medirStrain() {
  int16_t raw = ads.readADC_Differential_0_1();
  float vdiff = ads.computeVolts(raw);
  float mV_per_V = (vdiff / V_EXC) * 1000.0f;
  return mV_per_V * FACTOR_CAL;
}

float medirVoltaje() {
  int16_t raw = ads.readADC_Differential_0_1();
  return ads.computeVolts(raw);
}

void mostrarEnSerial(float comp, float bruto, float vdiff) {
  Serial.print("Strain: ");
  Serial.print(comp, 2);
  Serial.print(" µε | Vdiff: ");
  Serial.print(vdiff, 6);
  Serial.print(" V | Bruto: ");
  Serial.print(bruto, 2);
  Serial.print(" µε | Muestra #");
  Serial.println(sampleCount);
  sampleCount++;
}